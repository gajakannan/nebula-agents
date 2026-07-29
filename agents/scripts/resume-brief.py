#!/usr/bin/env python3
"""Emit the cold-start brief for resuming an evidence run.

A thread that picks up a run mid-flight has to reconstruct where it is. Doing
that by exploration is what makes long runs expensive: it costs many turns, and
everything it reads stays in context for every remaining turn.

Everything needed is already on disk — gate-state.json says which gates passed,
the action spec says what the next one requires, workstate.py holds the
decisions, STATUS.md names the current story, action-context.md carries scope.
This script assembles them into one brief so resuming costs a single read
instead of twenty, and states explicitly what must NOT be re-derived.

Writes Markdown to stdout: pipe it into a fresh session, or read it as the
first action of one.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment-dependent
    yaml = None


FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = FRAMEWORK_ROOT / "agents" / "actions" / "spec"
DEFAULT_WORKSTATE_NAME = "workstate.json"
DONE_STATUSES = {"done", "complete", "completed", "archived", "n/a", "skipped"}
STORY_ROW_RE = re.compile(r"^\|\s*(?P<id>[A-Z]\d+-S\d+)\s*\|(?P<title>[^|]*)\|(?P<status>[^|]*)\|")


class BriefError(ValueError):
    """Raised when the brief cannot be assembled."""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BriefError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BriefError(f"{path.name} is not valid JSON: {exc}") from exc


def next_stage(gate_state: dict) -> str | None:
    """The first stage not yet completed, in spec order.

    gate-state.json is keyed by stage id; dict order follows the order the
    runner wrote them, so sort to stay deterministic across replays.
    """
    stages = gate_state.get("stages") or {}
    for stage_id in sorted(stages, key=_stage_sort_key):
        if (stages[stage_id] or {}).get("status") != "completed":
            return stage_id
    return None


def _stage_sort_key(stage_id: str) -> tuple:
    match = re.match(r"^([A-Z]+)(\d+)(?:\.(\d+))?$", stage_id)
    if not match:
        return (stage_id, 0, 0)
    prefix, major, minor = match.groups()
    return (prefix, int(major), int(minor or 0))


def completed_stages(gate_state: dict) -> list[str]:
    stages = gate_state.get("stages") or {}
    return [
        stage_id
        for stage_id in sorted(stages, key=_stage_sort_key)
        if (stages[stage_id] or {}).get("status") == "completed"
    ]


def load_spec(action: str) -> dict:
    if yaml is None:
        raise BriefError("PyYAML is required to read the action spec")
    path = SPEC_DIR / f"{action}.yaml"
    if not path.is_file():
        raise BriefError(f"no action spec for {action!r}: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def find_gate(spec: dict, stage_id: str) -> dict | None:
    for gate in spec.get("gates") or []:
        if str(gate.get("id")) == stage_id:
            return gate
    return None


def describe_operations(gate: dict) -> list[str]:
    """One line per operation, in spec order, with the kind made explicit."""
    lines: list[str] = []
    for operation in gate.get("operations") or []:
        if not isinstance(operation, dict):
            continue
        for kind, body in operation.items():
            body = body or {}
            if kind == "run":
                argv = " ".join(str(token) for token in body.get("argv") or [])
                lines.append(f"run `{argv}` (cwd: {body.get('cwd', '?')})")
            elif kind == "write":
                lines.append(f"write `{body.get('artifact', '?')}`")
            elif kind == "checkpoint":
                lines.append(
                    f"CHECKPOINT `{body.get('id', '?')}` — {body.get('description', '')}"
                )
            else:
                lines.append(f"{kind}: {body}")
    return lines


def current_story(feature_path: Path) -> tuple[str, str, str] | None:
    """First story in STATUS.md's checklist whose status is not terminal.

    Scoped to the `## Story Checklist` section on purpose: STATUS.md also holds
    a Story x Role provenance matrix whose rows start with the same story id but
    whose second column is a role, not a title. Parsing the whole file picks up
    whichever table comes first and silently reports a role as the story title.
    """
    status_file = feature_path / "STATUS.md"
    if not status_file.is_file():
        return None
    sections = extract_sections(status_file, ["Story Checklist"])
    checklist = sections.get("Story Checklist")
    if not checklist:
        return None
    for line in checklist.splitlines():
        match = STORY_ROW_RE.match(line.strip())
        if not match:
            continue
        status = match.group("status").strip()
        if status.lower().strip("*` ") not in DONE_STATUSES:
            return match.group("id"), match.group("title").strip(), status
    return None


def extract_sections(markdown_path: Path, headings: list[str]) -> dict[str, str]:
    """Pull named `## ` sections out of a Markdown file, verbatim."""
    if not markdown_path.is_file():
        return {}
    wanted = {h.lower() for h in headings}
    found: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in markdown_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if current is not None:
                found[current] = "\n".join(buffer).strip()
            title = line[3:].strip()
            current = title if title.lower() in wanted else None
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    if current is not None:
        found[current] = "\n".join(buffer).strip()
    return found


def workstate_digest(product_root: Path, state_file: Path) -> dict | None:
    """Run `workstate.py digest --json`; None when unavailable.

    Calling the tool rather than parsing its state file keeps supersession
    handling in one place — the digest is already the supported read surface.
    """
    script = product_root / "scripts" / "kg" / "workstate.py"
    if not script.is_file() or not state_file.is_file():
        return None
    try:
        completed = subprocess.run(
            [sys.executable, str(script), "--state-file", str(state_file), "digest", "--json"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- (none recorded)"]


def build_brief(
    *,
    run_id: str,
    run_folder: Path,
    product_root: Path,
    gate_state: dict,
    manifest: dict,
    spec: dict,
    stage_id: str | None,
    digest: dict | None,
    story: tuple[str, str, str] | None,
    context_sections: dict[str, str],
    feature_rel: str | None,
) -> str:
    action = gate_state.get("action") or manifest.get("action") or "feature"
    done = completed_stages(gate_state)
    out: list[str] = []

    out.append(f"# Resume brief — {run_id}")
    out.append("")
    out.append(
        "Cold-start context for this run, assembled from evidence on disk. "
        "Treat it as authoritative: do not re-derive what it states."
    )
    out.append("")

    out.append("## Where you are")
    out.append("")
    out.append(f"- **action:** {action}")
    if manifest.get("feature_id"):
        out.append(f"- **feature:** {manifest['feature_id']} — {manifest.get('feature_slug', '')}")
    out.append(f"- **manifest status:** {manifest.get('status', 'unknown')}")
    out.append(f"- **run folder:** {run_folder}")
    out.append(f"- **gates completed:** {' '.join(done) if done else '(none)'}")
    out.append(f"- **next gate:** {stage_id or 'all gates complete — run is at closeout'}")
    out.append("")

    gate = find_gate(spec, stage_id) if stage_id else None
    if gate:
        out.append(f"## Next gate: {gate.get('id')} — {gate.get('title', '')}")
        out.append("")
        out.append(f"- **role:** {gate.get('role', '?')}")
        if gate.get("role_switch"):
            out.append(f"- **MUST switch role — read:** `{gate['role_switch']}`")
        if gate.get("artifacts"):
            out.append(f"- **artifacts to produce:** {', '.join(gate['artifacts'])}")
        if gate.get("manifest_status_after"):
            out.append(f"- **manifest status after:** {gate['manifest_status_after']}")
        operations = describe_operations(gate)
        if operations:
            out.append("- **operations, in order:**")
            out.extend(f"  - {line}" for line in operations)
        if gate.get("judgment"):
            out.append("")
            out.append("**Judgment for this gate:**")
            out.append("")
            out.append(str(gate["judgment"]).strip())
        out.append("")

    out.append("## Decisions already made")
    out.append("")
    if digest:
        out.extend(_bullets([str(d) for d in digest.get("decided") or []]))
        out.append("")
        out.append("## Open questions")
        out.append("")
        out.extend(_bullets([str(q) for q in digest.get("next") or []]))
    else:
        out.append(
            "- (no workstate recorded — decisions made in this run were not captured, "
            "so anything not in the evidence artifacts is lost)"
        )
    out.append("")

    if story:
        story_id, title, status = story
        out.append("## Current story")
        out.append("")
        out.append(f"- **{story_id}** — {title} (status: {status})")
        if feature_rel:
            out.append(f"- spec: `{feature_rel}/{story_id}-*.md`")
        out.append("")

    for heading, body in context_sections.items():
        if body:
            out.append(f"## {heading}")
            out.append("")
            out.append(body)
            out.append("")

    forbidden = spec.get("forbidden") or []
    if forbidden:
        out.append("## Forbidden in this action")
        out.append("")
        out.extend(f"- {item}" for item in forbidden)
        out.append("")

    out.append("## Read these, in order")
    out.append("")
    reads = [f"`{run_folder.name}/action-context.md` — run identity, assumptions, scope"]
    if feature_rel:
        reads.append(f"`{feature_rel}/feature-assembly-plan.md` — the implementation spec")
        if story:
            reads.append(f"`{feature_rel}/{story[0]}-*.md` — the story you are on")
    if gate and gate.get("role_switch"):
        reads.append(f"`{gate['role_switch']}` — the role you must switch to")
    out.extend(f"{i}. {item}" for i, item in enumerate(reads, start=1))
    out.append("")

    out.append("## Do not re-read")
    out.append("")
    out.append(
        "- **Validator and runner sources** (`validate-feature-evidence.py`, `run-gate.py`, "
        "`lookup.py`). Run the gate and read its error output; the message names the rule."
    )
    out.append(
        "- **commands.log or whole manifests.** Query them with `jq`/`rg` for the one field "
        "you need — printing them puts the whole file in context for the rest of the run."
    )
    out.append(
        "- **Anything stated above.** It came from the evidence; re-reading the source "
        "costs context and changes nothing."
    )
    out.append("")

    return "\n".join(out)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit the cold-start brief for resuming an evidence run."
    )
    parser.add_argument("--run-id", required=True, help="Evidence run id to brief.")
    add_product_root_arg(parser)
    parser.add_argument(
        "--stage",
        help="Brief for this gate instead of the first incomplete one.",
    )
    parser.add_argument(
        "--workstate",
        help=f"Path to the workstate file. Default: <run folder>/{DEFAULT_WORKSTATE_NAME}.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        product_root = resolve_product_root(args.product_root)
        run_folder = (
            product_root / "planning-mds" / "operations" / "evidence" / "runs" / args.run_id
        )
        if not run_folder.is_dir():
            raise BriefError(f"run folder does not exist: {run_folder}")

        gate_state = _read_json(run_folder / "gate-state.json")
        manifest = _read_json(run_folder / "evidence-manifest.json")
        action = gate_state.get("action") or manifest.get("action") or "feature"
        spec = load_spec(str(action))

        stage_id = args.stage or next_stage(gate_state)
        if args.stage and not find_gate(spec, args.stage):
            raise BriefError(f"{args.stage!r} is not a gate in the {action} spec")

        feature_rel = manifest.get("feature_path_at_closeout") or manifest.get(
            "feature_path_at_run_start"
        )
        feature_path = product_root / feature_rel if feature_rel else None

        state_file = (
            Path(args.workstate).expanduser()
            if args.workstate
            else run_folder / DEFAULT_WORKSTATE_NAME
        )

        brief = build_brief(
            run_id=args.run_id,
            run_folder=run_folder,
            product_root=product_root,
            gate_state=gate_state,
            manifest=manifest,
            spec=spec,
            stage_id=stage_id,
            digest=workstate_digest(product_root, state_file),
            story=current_story(feature_path) if feature_path else None,
            context_sections=extract_sections(
                run_folder / "action-context.md", ["Assumptions", "Scope Boundaries"]
            ),
            feature_rel=feature_rel,
        )
        print(brief)
    except BriefError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
