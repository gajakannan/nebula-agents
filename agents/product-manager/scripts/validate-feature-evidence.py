#!/usr/bin/env python3
"""Validate completed-feature evidence packages.

Phase 1 implemented the validator shell, invocation `_fails`, eligibility
classification, run resolution, and lightweight manifest/latest-run parsing.

Phase 2a adds single-run validator checks: required-artifact presence (§10),
required-heading presence (§14), manifest schema depth (§11 path/boolean/waiver
rules), `commands.log` JSONL + secret-pattern scanning (§13), `gate-decisions.md`
stage row presence (§17), `lifecycle-gates.log` schema, the §15 PM Acceptance
Line Format parser, `effective_date_overridden_warns`, and the `rerun_of` /
`changed_paths` shape rules.

Cross-artifact (§21), full role/gate verdict reconciliation (§11/§14), STATUS.md
current-signoff logic (§16), tracker integration, and the validator-defect
downgrade algorithm (§22) land in Phase 2b.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable


DEFAULT_EFFECTIVE_DATE = date(2026, 5, 19)
# Runs whose contract_effective_date is on/after this date must record a
# complete `security_scans` block when security_sensitive_scope is true (QE
# runs the scanners, Security owns the verdict). Earlier runs are exempt so
# pre-existing/archived evidence packages stay valid.
SECURITY_SCANS_EFFECTIVE_DATE = date(2026, 5, 25)
REQUIRED_SECURITY_SCAN_CLASSES = ("dependency", "secrets", "sast", "dast")
# Runs whose contract_effective_date is on/after this date must carry the
# architect's G7 knowledge-graph reconciliation: `kg-reconciliation.md` plus
# `gate_results.kg_reconciliation`. Earlier runs are exempt so pre-existing
# evidence packages (e.g. F0036, effective 2026-05-25) stay valid.
KG_RECONCILIATION_EFFECTIVE_DATE = date(2026, 6, 1)
# Runs whose contract_effective_date is on/after this date must prove the
# generated knowledge-graph layers were rebuilt, not merely checked from a
# previously committed snapshot. Earlier evidence packages stay valid under
# their original weaker contract.
KG_GENERATED_REGEN_EFFECTIVE_DATE = date(2026, 7, 5)
# Runs whose contract_effective_date is on/after this date author the graph as
# kg-source/** shards and regenerate the projection trio + trackers via
# `compile.py` (F0006 compiled-projection cutover). The generated-KG matcher
# accepts `compile.py` (and `validate.py --check-reproducible`) as the sanctioned
# regeneration entry point for those runs; earlier runs keep the
# `validate.py --regenerate-*` contract so their evidence stays valid.
KG_COMPILE_PROJECTION_EFFECTIVE_DATE = date(2026, 7, 11)
RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]{8}$")
FEATURE_ID_RE = re.compile(r"^F\d{4}$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STAGES = {"G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "closeout"}
TERMINAL_ACTIVE_STATES = {"done", "complete", "completed", "archived"}
MANIFEST_STATUSES = {"draft", "in-progress", "approved", "superseded"}
SUPPORTED_MANIFEST_SCHEMA_VERSIONS = {1}
FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
TERMINAL_FEATURE_STATES = {"done", "completed", "archived"}
RETIRED_FEATURE_STATES = {"abandoned", "superseded"}
PRODUCT_ROOT_ARTIFACT_PREFIXES = ("planning-mds", "engine", "experience", "neuron", "bruno", "scripts")

# §10 artifact dependency on the manifest scope booleans.
RUNTIME_PREFLIGHT_FILE = "g1-runtime-preflight.md"
SECURITY_REVIEW_FILE = "security-review-report.md"

# §14 required headings per role/base file (case-insensitive match).
REQUIRED_HEADINGS: dict[str, list[str]] = {
    "README.md": ["Run Summary", "Status", "Evidence Index", "Validation Summary", "Open Follow-ups"],
    "action-context.md": ["Run Identity", "Inputs", "Assumptions", "Scope Boundaries", "Lifecycle Stage"],
    "artifact-trace.md": [
        "Artifacts Read",
        "Artifacts Created Or Updated",
        "Generated Evidence",
        "External Or Global Evidence References",
        "Omissions And Waivers",
    ],
    "g2-self-review.md": [
        "Scope Review",
        "Acceptance Criteria Review",
        "Implementation Risks",
        "Validation Evidence",
    ],
    "signoff-ledger.md": [
        "Required Role Matrix",
        "Current Signoff State",
        "Recommendation Acceptances",
        "Waivers And Omissions",
    ],
    "pm-closeout.md": [
        "Final Story Status",
        "Archive Decision",
        "Deferred Follow-ups",
        "Recommendation Acceptances",
        "Tracker Updates",
        "Validator Results",
    ],
    "kg-reconciliation.md": [
        "Binding Delta",
        "Canonical Nodes",
        "Validator Results",
        "Handoff to Closeout",
    ],
}

# §17 stage matrix — which gate rows must appear in gate-decisions.md by stage.
STAGE_REQUIRED_GATES: dict[str, list[str]] = {
    "G0": ["G0"],
    "G1": ["G0", "G1"],
    "G2": ["G0", "G1", "G2"],
    "G3": ["G0", "G1", "G2", "G3"],
    "G4": ["G0", "G1", "G2", "G3", "G4"],
    "G5": ["G0", "G1", "G2", "G3", "G4", "G5"],
    "G6": ["G0", "G1", "G2", "G3", "G4", "G5", "G6"],
    "G7": ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"],
    "G8": ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"],
    "closeout": ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"],
}


def kg_reconciliation_required(manifest: dict[str, Any], stage: str) -> bool:
    """Whether this run must carry the G7 KG reconciliation package."""
    manifest_effective = parse_iso_date(str(manifest.get("contract_effective_date", "")))
    return (
        stage in {"G7", "G8", "closeout"}
        and manifest_effective is not None
        and manifest_effective >= KG_RECONCILIATION_EFFECTIVE_DATE
    )


def kg_generated_regeneration_required(manifest: dict[str, Any], stage: str) -> bool:
    """Whether this run must prove fresh generated-KG regeneration."""
    manifest_effective = parse_iso_date(str(manifest.get("contract_effective_date", "")))
    return (
        kg_reconciliation_required(manifest, stage)
        and manifest_effective is not None
        and manifest_effective >= KG_GENERATED_REGEN_EFFECTIVE_DATE
    )


def compile_projection_contract(manifest: dict[str, Any]) -> bool:
    """Whether this run is under the compiled-projection contract (F0006): the graph is authored as
    kg-source/** shards and the trio+trackers are regenerated via compile.py."""
    manifest_effective = parse_iso_date(str(manifest.get("contract_effective_date", "")))
    return manifest_effective is not None and manifest_effective >= KG_COMPILE_PROJECTION_EFFECTIVE_DATE


def _command_compiles_projection(command: str) -> bool:
    """A command that regenerates the compiled projection trio + tracker regions (F0006-S0009)."""
    c = command.casefold()
    return "compile.py" in c or ("validate.py" in c and "--check-reproducible" in c)


# §10 / §17 — which run-folder files must exist for a given stage.
def stage_required_files(stage: str, runtime_bearing: bool, security_required: bool) -> list[str]:
    base = [
        "README.md",
        "action-context.md",
        "artifact-trace.md",
        "gate-decisions.md",
        "commands.log",
        "lifecycle-gates.log",
        "evidence-manifest.json",
        "g0-assembly-plan-validation.md",
    ]
    if stage == "G0":
        return base
    if runtime_bearing:
        base.append(RUNTIME_PREFLIGHT_FILE)
    if stage == "G1":
        return base
    base += [
        "g2-self-review.md",
        "test-plan.md",
        "test-execution-report.md",
        "coverage-report.md",
        "deployability-check.md",
    ]
    if stage == "G2":
        return base
    base.append("code-review-report.md")
    if security_required:
        base.append(SECURITY_REVIEW_FILE)
    if stage == "G3":
        return base
    if stage == "G4":
        return base
    base.append("signoff-ledger.md")
    if stage == "G5":
        return base
    base.append("feature-action-execution.md")
    if stage == "G6":
        return base
    if stage == "G7":
        return base
    base.append("pm-closeout.md")
    return base


# §7 path-class globs (framework default). Each glob maps to the booleans it forces.
DEFAULT_PATH_CLASSES: dict[str, set[str]] = {
    "experience/**": {"frontend_in_scope"},
    "engine/**": {"runtime_bearing"},
    "engine/**/Migrations/**": {"runtime_bearing", "deployment_config_changed"},
    "**/migrations/**": {"runtime_bearing", "deployment_config_changed"},
    "**/Dockerfile": {"deployment_config_changed"},
    "**/Dockerfile.*": {"deployment_config_changed"},
    "**/docker-compose*.y?ml": {"deployment_config_changed"},
    ".github/workflows/**": {"deployment_config_changed"},
    "ci/**": {"deployment_config_changed"},
    "**/appsettings*.json": {"deployment_config_changed"},
    "**/.env*": {"deployment_config_changed"},
    "**/config/**": {"deployment_config_changed"},
    "**/Auth*/**": {"security_sensitive_scope"},
    "**/Identity*/**": {"security_sensitive_scope"},
    "**/Permissions/**": {"security_sensitive_scope"},
    "**/Security/**": {"security_sensitive_scope"},
    "**/Secrets/**": {"security_sensitive_scope"},
    "**/Tests/**": {"runtime_bearing"},
    "**/*.Tests/**": {"runtime_bearing"},
    "experience/**/*.test.*": {"runtime_bearing"},
    "experience/**/*.spec.*": {"runtime_bearing"},
}

REGEX_FLAG_NAMES = {"ignorecase": re.IGNORECASE, "multiline": re.MULTILINE}
RECOGNIZED_WAIVER_KEYS = {"coverage", "validator_defect"}

# §11 / §14 verdict whitelists.
PASSING_PASS_RESULTS = {"PASS", "PASS WITH RECOMMENDATIONS"}
PASSING_APPROVED_RESULTS = {"APPROVED", "APPROVED WITH RECOMMENDATIONS"}
ROLE_PASSING_REVIEWS = PASSING_APPROVED_RESULTS | PASSING_PASS_RESULTS


# §11 gate_results requirement matrix.
GATE_SPEC: dict[str, dict[str, Any]] = {
    "assembly_plan_validation": {
        "stages": {"G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "closeout"},
        "passing": PASSING_PASS_RESULTS,
        "artifact": "g0-assembly-plan-validation.md",
        "condition": "always",
    },
    "runtime_preflight": {
        "stages": {"G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "closeout"},
        "passing": PASSING_PASS_RESULTS,
        "artifact": "g1-runtime-preflight.md",
        "condition": "runtime_bearing",
    },
    "self_review": {
        "stages": {"G2", "G3", "G4", "G5", "G6", "G7", "G8", "closeout"},
        "passing": PASSING_PASS_RESULTS,
        "artifact": "g2-self-review.md",
        "condition": "always",
    },
    "deployability": {
        "stages": {"G2", "G3", "G4", "G5", "G6", "G7", "G8", "closeout"},
        "passing": PASSING_PASS_RESULTS,
        "artifact": "deployability-check.md",
        "condition": "always",
    },
    "signoff": {
        "stages": {"G5", "G6", "G7", "G8", "closeout"},
        "passing": PASSING_PASS_RESULTS,
        "artifact": "signoff-ledger.md",
        "condition": "always",
    },
    "pm_closeout": {
        "stages": {"G8", "closeout"},
        "passing": PASSING_APPROVED_RESULTS,
        "artifact": "pm-closeout.md",
        "condition": "always",
    },
    "tracker_sync": {
        "stages": {"G8", "closeout"},
        "passing": PASSING_PASS_RESULTS,
        "artifact": "lifecycle-gates.log",
        "condition": "always",
    },
    "kg_reconciliation": {
        "stages": {"G7", "G8", "closeout"},
        "passing": PASSING_PASS_RESULTS,
        "artifact": "kg-reconciliation.md",
        "condition": "always",
    },
}

# §11 role_results requirement matrix.
ROLE_SPEC: dict[str, dict[str, Any]] = {
    "Quality Engineer": {
        "required_artifacts": ["test-plan.md", "test-execution-report.md", "coverage-report.md"],
        "verdict_artifact": "test-execution-report.md",
        "passing": PASSING_PASS_RESULTS,
        "condition": "always",
        "stages": {"G2", "G3", "G4", "G5", "G6", "G7", "G8", "closeout"},
    },
    "Code Reviewer": {
        "required_artifacts": ["code-review-report.md"],
        "verdict_artifact": "code-review-report.md",
        "passing": ROLE_PASSING_REVIEWS,
        "condition": "always",
        "stages": {"G3", "G4", "G5", "G6", "G7", "G8", "closeout"},
    },
    "Security Reviewer": {
        "required_artifacts": ["security-review-report.md"],
        "verdict_artifact": "security-review-report.md",
        "passing": PASSING_PASS_RESULTS,
        "condition": "security",
        "stages": {"G3", "G4", "G5", "G6", "G7", "G8", "closeout"},
    },
    "DevOps": {
        "required_artifacts": ["deployability-check.md"],
        "verdict_artifact": "deployability-check.md",
        "passing": PASSING_PASS_RESULTS,
        "condition": "devops",
        "stages": {"G2", "G3", "G4", "G5", "G6", "G7", "G8", "closeout"},
    },
    "Architect": {
        "required_artifacts": ["g0-assembly-plan-validation.md"],
        "verdict_artifact": "g0-assembly-plan-validation.md",
        "passing": PASSING_PASS_RESULTS,
        "condition": "status_required",
        "stages": {"G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "closeout"},
    },
}


def effective_required_roles(manifest: dict[str, Any], status_required: set[str]) -> set[str]:
    """Compute the effective required role set from booleans + STATUS.md."""
    roles = {"Quality Engineer", "Code Reviewer"}
    if manifest.get("security_sensitive_scope") or "Security Reviewer" in status_required:
        roles.add("Security Reviewer")
    if manifest.get("deployment_config_changed") or "DevOps" in status_required:
        roles.add("DevOps")
    if "Architect" in status_required:
        roles.add("Architect")
    return roles


def gate_required_at_stage(key: str, stage: str, runtime_bearing: bool) -> bool:
    spec = GATE_SPEC.get(key)
    if spec is None:
        return False
    if stage not in spec["stages"]:
        return False
    if spec["condition"] == "runtime_bearing":
        return runtime_bearing
    return True


def role_required_at_stage(role: str, stage: str, manifest: dict[str, Any], status_required: set[str]) -> bool:
    spec = ROLE_SPEC.get(role)
    if spec is None:
        return False
    if stage not in spec["stages"]:
        return False
    condition = spec["condition"]
    if condition == "always":
        return True
    if condition == "security":
        return bool(manifest.get("security_sensitive_scope")) or "Security Reviewer" in status_required
    if condition == "devops":
        return bool(manifest.get("deployment_config_changed")) or "DevOps" in status_required
    if condition == "status_required":
        return role in status_required
    return False


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #


@dataclass
class Finding:
    rule_id: str
    message: str
    feature: str | None = None
    run_id: str | None = None
    path: str | None = None

    def to_json(self) -> dict[str, str]:
        payload = {"rule_id": self.rule_id, "message": self.message}
        if self.feature:
            payload["feature"] = self.feature
        if self.run_id:
            payload["run_id"] = self.run_id
        if self.path:
            payload["path"] = self.path
        return payload


@dataclass
class Result:
    stage: str
    product_root: Path
    effective_date: date
    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    info: list[Finding] = field(default_factory=list)
    features_validated: int = 0
    features_skipped_pre_contract_archived: int = 0
    features_skipped_active_done_pre_contract: int = 0
    features_skipped_retired_abandoned: int = 0
    features_skipped_retired_superseded: int = 0

    def add_error(self, rule_id: str, message: str, **kwargs: str) -> None:
        self.errors.append(Finding(rule_id, message, **kwargs))

    def add_warning(self, rule_id: str, message: str, **kwargs: str) -> None:
        self.warnings.append(Finding(rule_id, message, **kwargs))

    def add_info(self, rule_id: str, message: str, **kwargs: str) -> None:
        self.info.append(Finding(rule_id, message, **kwargs))

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "validator": "validate-feature-evidence",
            "stage": self.stage,
            "product_root": str(self.product_root),
            "effective_date": self.effective_date.isoformat(),
            "features_validated": self.features_validated,
            "features_skipped_pre_contract_archived": self.features_skipped_pre_contract_archived,
            "features_skipped_active_done_pre_contract": self.features_skipped_active_done_pre_contract,
            "features_skipped_retired_abandoned": self.features_skipped_retired_abandoned,
            "features_skipped_retired_superseded": self.features_skipped_retired_superseded,
            "errors": [finding.to_json() for finding in self.errors],
            "warnings": [finding.to_json() for finding in self.warnings],
            "info": [finding.to_json() for finding in self.info],
        }


@dataclass(frozen=True)
class ArtifactResolution:
    original: str
    normalized_path: Path | None
    display_path: str
    exists: bool
    warning_kind: str | None = None
    error_kind: str | None = None
    is_url: bool = False


@dataclass(frozen=True)
class RegistryRow:
    section: str
    feature_id: str
    raw: dict[str, str]

    @property
    def folder(self) -> str:
        return strip_code(self.raw.get("Folder", ""))

    @property
    def evidence_slug(self) -> str:
        cleaned = self.folder.rstrip("/")
        if cleaned.startswith("archive/"):
            cleaned = cleaned[len("archive/") :]
        return cleaned or self.feature_id

    @property
    def status(self) -> str:
        return self.raw.get("Status", "").strip()


# --------------------------------------------------------------------------- #
# Generic parsing helpers
# --------------------------------------------------------------------------- #


def strip_code(value: str) -> str:
    return value.strip().strip("`").strip()


def parse_iso_date(value: str) -> date | None:
    cleaned = strip_code(value)
    if not ISO_DATE_RE.fullmatch(cleaned):
        return None
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        return None


def normalize_heading(value: str) -> str:
    return value.strip().casefold()


def parse_table(section: str) -> list[dict[str, str]]:
    """Parse a Markdown pipe table; returns row dicts keyed by header text."""
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []
    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def extract_section(content: str, heading: str, level: int | None = None) -> str:
    """Return everything between `heading` and the next heading of equal/higher level."""
    target = normalize_heading(heading)
    matches = list(HEADING_RE.finditer(content))
    for index, match in enumerate(matches):
        if normalize_heading(match.group(2)) != target:
            continue
        if level is not None and len(match.group(1)) != level:
            continue
        start = match.end()
        current_level = len(match.group(1))
        end = len(content)
        for follow in matches[index + 1 :]:
            if len(follow.group(1)) <= current_level:
                end = follow.start()
                break
        return content[start:end]
    return ""


def collect_headings(content: str) -> set[str]:
    return {normalize_heading(match.group(2)) for match in HEADING_RE.finditer(content)}


def headings_present(content: str, required: Iterable[str]) -> list[str]:
    present = collect_headings(content)
    return [heading for heading in required if normalize_heading(heading) not in present]


def safe_read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _command_regenerates_symbols(command: str) -> bool:
    command_lower = command.casefold()
    return (
        ("validate.py" in command_lower and "--regenerate-symbols" in command_lower)
        or "symbols.py" in command_lower
    )


def _command_checks_symbols(command: str) -> bool:
    command_lower = command.casefold()
    return "validate.py" in command_lower and "--check-symbols" in command_lower


def _command_regenerates_decisions(command: str) -> bool:
    command_lower = command.casefold()
    return (
        ("validate.py" in command_lower and "--regenerate-decisions" in command_lower)
        or "decisions.py" in command_lower
    )


def _command_checks_decisions(command: str) -> bool:
    command_lower = command.casefold()
    return "validate.py" in command_lower and "--check-decisions" in command_lower


def _command_writes_coverage_report(command: str) -> bool:
    command_lower = command.casefold()
    return "validate.py" in command_lower and "--write-coverage-report" in command_lower


def successful_kg_generated_command_flags(commands_log: Path) -> dict[str, bool]:
    """Return which generated-KG commands have successful commands.log evidence."""
    content = safe_read(commands_log)
    flag_names = (
        "symbol regeneration",
        "symbol validation",
        "decision regeneration",
        "decision validation",
        "coverage report regeneration",
    )
    if content is None:
        return {flag: False for flag in flag_names}

    results = {flag: False for flag in flag_names}
    for raw_line in content.splitlines():
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or record.get("exit_code") != 0:
            continue
        command = record.get("command")
        if not isinstance(command, str):
            continue
        results["symbol regeneration"] = (
            results["symbol regeneration"] or _command_regenerates_symbols(command)
        )
        results["symbol validation"] = results["symbol validation"] or _command_checks_symbols(command)
        results["decision regeneration"] = (
            results["decision regeneration"] or _command_regenerates_decisions(command)
        )
        results["decision validation"] = results["decision validation"] or _command_checks_decisions(command)
        results["coverage report regeneration"] = (
            results["coverage report regeneration"] or _command_writes_coverage_report(command)
        )
    return results


def load_json_file(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"unparseable JSON: {exc}"
    except OSError as exc:
        return None, f"read error: {exc}"


def _path_from_reference(value: str) -> Path:
    parts = [part for part in value.replace("\\", "/").split("/") if part]
    return Path(*parts) if parts else Path()


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _is_url_reference(value: str) -> bool:
    # Existing behavior skipped command artifacts beginning with "http".
    return value.strip().startswith("http")


def _is_absolute_reference(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return normalized.startswith("/") or bool(re.match(r"^[A-Za-z]:/", normalized))


def _contains_parent_reference(value: str) -> bool:
    return ".." in [part for part in value.replace("\\", "/").split("/") if part]


def _relative_to_product_root(product_root: Path, target: Path) -> str:
    try:
        return target.resolve(strict=False).relative_to(product_root.resolve(strict=False)).as_posix()
    except ValueError:
        return str(target)


def _is_under_product_root(product_root: Path, target: Path) -> bool:
    try:
        target.resolve(strict=False).relative_to(product_root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _recognized_product_suffix(value: str) -> str | None:
    parts = [part for part in value.replace("\\", "/").split("/") if part]
    for index, part in enumerate(parts):
        if part in PRODUCT_ROOT_ARTIFACT_PREFIXES:
            return "/".join(parts[index:])
    return None


def _is_scratch_reference(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return normalized in {"/tmp", "/var/tmp"} or normalized.startswith(("/tmp/", "/var/tmp/"))


def _relative_artifact_target(product_root: Path, run_folder: Path | None, value: str) -> Path:
    cleaned = value.replace("\\", "/").lstrip("./")
    first = next((part for part in cleaned.split("/") if part), "")
    base = product_root if run_folder is None or first in PRODUCT_ROOT_ARTIFACT_PREFIXES else run_folder
    return base / _path_from_reference(cleaned)


def resolve_artifact_reference(product_root: Path, run_folder: Path | None, value: str) -> ArtifactResolution:
    cleaned = strip_code(value)
    if not cleaned:
        return ArtifactResolution(value, None, value, False, error_kind="artifact_missing_fails")
    if _is_url_reference(cleaned):
        return ArtifactResolution(value, None, cleaned, True, is_url=True)

    if cleaned.startswith("{PRODUCT_ROOT}"):
        suffix = cleaned[len("{PRODUCT_ROOT}") :].lstrip("/\\")
        target = product_root / _path_from_reference(suffix)
        exists = _path_exists(target)
        return ArtifactResolution(
            value,
            target,
            _relative_to_product_root(product_root, target),
            exists,
            warning_kind="placeholder_artifact_path_normalized_warns" if exists else None,
            error_kind=None if exists else "artifact_missing_fails",
        )

    if _contains_parent_reference(cleaned):
        return ArtifactResolution(value, None, cleaned, False, error_kind="artifact_missing_fails")

    if _is_absolute_reference(cleaned):
        normalized = cleaned.replace("\\", "/")
        if normalized.startswith("/"):
            absolute_target = Path(normalized)
            if _is_under_product_root(product_root, absolute_target):
                exists = _path_exists(absolute_target)
                return ArtifactResolution(
                    value,
                    absolute_target,
                    _relative_to_product_root(product_root, absolute_target),
                    exists,
                    warning_kind="absolute_artifact_under_product_root_warns" if exists else None,
                    error_kind=None if exists else "artifact_missing_fails",
                )
        if _is_scratch_reference(cleaned):
            return ArtifactResolution(value, None, cleaned, False, error_kind="scratch_artifact_fails")
        suffix = _recognized_product_suffix(cleaned)
        if suffix:
            target = product_root / _path_from_reference(suffix)
            exists = _path_exists(target)
            return ArtifactResolution(
                value,
                target,
                _relative_to_product_root(product_root, target),
                exists,
                warning_kind="legacy_absolute_artifact_relocated_warns" if exists else None,
                error_kind=None if exists else "artifact_missing_fails",
            )
        return ArtifactResolution(value, None, cleaned, False, error_kind="unmappable_absolute_artifact_fails")

    target = _relative_artifact_target(product_root, run_folder, cleaned)
    exists = _path_exists(target)
    return ArtifactResolution(
        value,
        target,
        _relative_to_product_root(product_root, target),
        exists,
        error_kind=None if exists else "artifact_missing_fails",
    )


def add_artifact_resolution_warning(
    result: Result,
    resolution: ArtifactResolution,
    context: str,
    **common: str,
) -> None:
    if not resolution.warning_kind:
        return
    result.add_warning(
        resolution.warning_kind,
        f"{context} {resolution.original!r} normalized to {resolution.display_path!r}",
        **common,
    )


def add_artifact_resolution_error(
    result: Result,
    resolution: ArtifactResolution,
    context: str,
    **common: str,
) -> None:
    if not resolution.error_kind:
        return
    if resolution.error_kind == "scratch_artifact_fails":
        message = f"{context} {resolution.original!r} is a scratch/local path and is not durable evidence"
    elif resolution.error_kind == "unmappable_absolute_artifact_fails":
        message = f"{context} {resolution.original!r} is absolute and cannot be mapped to the current product root"
    else:
        message = f"{context} {resolution.original!r} does not resolve to an existing artifact"
        if resolution.display_path and resolution.display_path != resolution.original:
            message += f" at {resolution.display_path!r}"
    result.add_error(resolution.error_kind, message, **common)


def validate_artifact_reference(
    result: Result,
    product_root: Path,
    run_folder: Path | None,
    value: str,
    context: str,
    *,
    missing_rule_id: str | None = None,
    missing_message: str | None = None,
    generic_missing: bool = True,
    **common: str,
) -> ArtifactResolution:
    resolution = resolve_artifact_reference(product_root, run_folder, value)
    if resolution.is_url:
        return resolution
    add_artifact_resolution_warning(result, resolution, context, **common)
    if resolution.error_kind == "artifact_missing_fails":
        if generic_missing:
            add_artifact_resolution_error(result, resolution, context, **common)
        if missing_rule_id:
            result.add_error(
                missing_rule_id,
                missing_message or f"{context} {value!r} does not resolve",
                **common,
            )
    elif resolution.error_kind:
        add_artifact_resolution_error(result, resolution, context, **common)
    return resolution


def artifact_references(content: str, relative_prefix: str) -> list[str]:
    prefix = re.escape(relative_prefix)
    pattern = re.compile(rf"(?:\{{PRODUCT_ROOT\}}[\\/]|[A-Za-z]:[\\/]|/)?[^\s)\]]*{prefix}[^\s)\]]+")
    return pattern.findall(content)


# --------------------------------------------------------------------------- #
# §15 PM Acceptance Line Format
# --------------------------------------------------------------------------- #


# A line of the form `- Accepted: <identifier> — <details>` (§15).
# Separator is em-dash OR hyphen-minus, but in either case it MUST have
# surrounding whitespace so a hyphen inside an identifier (e.g. `custom-key`)
# is not mistakenly treated as the separator.
PM_ACCEPTANCE_LINE_RE = re.compile(
    r"""
    ^\s*-\s+                       # bullet
    accepted:\s*                   # keyword (case-insensitive)
    (?P<identifier>\S(?:.*?\S)?)   # identifier (no leading/trailing space, lazy)
    \s+[—-]\s+                     # em-dash or hyphen-minus with required surrounding spaces
    (?P<details>.+?)\s*$           # details
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)


@dataclass(frozen=True)
class PmAcceptance:
    identifier: str
    details: str


def parse_pm_acceptance_lines(content: str) -> list[PmAcceptance]:
    """Parse §15 PM Acceptance Line Format from markdown text.

    Honors both em-dash (U+2014) and hyphen-minus separators and is
    case-insensitive on the `Accepted:` keyword. Returns one entry per line;
    table-cell shapes are accepted only when the cell contains the bullet form.
    """
    results: list[PmAcceptance] = []
    for match in PM_ACCEPTANCE_LINE_RE.finditer(content):
        identifier = match.group("identifier").strip()
        details = match.group("details").strip()
        if not identifier or not details:
            continue
        results.append(PmAcceptance(identifier=identifier, details=details))
    return results


# --------------------------------------------------------------------------- #
# §15 Recommendation structure
# --------------------------------------------------------------------------- #


SEVERITY_VALUES = {"low", "medium", "high", "critical"}
BLOCKING_SEVERITIES = {"high", "critical"}

# Canonical bullet: `- [severity] text — owner: X; follow-up: Y`.
# Optional severity tag, optional disposition tail.
RECOMMENDATION_BULLET_RE = re.compile(
    r"""
    ^\s*-\s+                                # bullet
    (?:\[(?P<severity>[^\]\n]+)\]\s+)?      # optional [severity] tag
    (?P<text>.+?)                            # recommendation text (lazy)
    (?:                                      # optional disposition
        \s+[—-]\s+
        owner:\s*(?P<owner>[^;\n]+?)\s*;\s*
        follow-up:\s*(?P<followup>[^\n]+?)
    )?
    \s*$
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)


@dataclass(frozen=True)
class Recommendation:
    severity: str | None  # lower-cased if present
    severity_raw: str | None  # the raw tag as authored
    text: str
    owner: str | None
    follow_up: str | None
    raw: str

    @property
    def has_disposition(self) -> bool:
        return self.owner is not None and self.follow_up is not None


def _find_recommendations_section(content: str) -> str:
    """Locate the most likely Recommendations section in a role report."""
    for heading in ("Recommendations", "Findings", "Recommendation Acceptances"):
        section = extract_section(content, heading)
        if section:
            return section
    return ""


def parse_recommendations(content: str) -> list[Recommendation]:
    """Parse recommendation bullets from a role report.

    Looks inside a `Recommendations` (or `Findings`) section first; falls back
    to scanning the whole document for bullets that carry either a `[severity]`
    tag or an `owner:`/`follow-up:` disposition.
    """
    target_section = _find_recommendations_section(content) or content
    recs: list[Recommendation] = []
    for match in RECOMMENDATION_BULLET_RE.finditer(target_section):
        severity_raw = match.group("severity")
        owner = match.group("owner")
        # Only treat as a recommendation if it has *some* structural marker —
        # severity tag OR explicit owner — so we don't mistake every bullet for
        # a recommendation.
        if not severity_raw and not owner:
            continue
        severity = severity_raw.strip().lower() if severity_raw else None
        recs.append(
            Recommendation(
                severity=severity,
                severity_raw=severity_raw.strip() if severity_raw else None,
                text=match.group("text").strip(),
                owner=owner.strip() if owner else None,
                follow_up=match.group("followup").strip() if match.group("followup") else None,
                raw=match.group(0).strip(),
            )
        )
    return recs


VERDICT_LINE_RE = re.compile(r"^\s*\*{0,2}Result\*{0,2}:\s*(?P<verdict>.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def extract_verdict(content: str) -> str | None:
    """Find the first `Result: <verdict>` line in a role report."""
    match = VERDICT_LINE_RE.search(content)
    if not match:
        return None
    return match.group("verdict").strip()


# --------------------------------------------------------------------------- #
# Secret-pattern scanning
# --------------------------------------------------------------------------- #


def compile_regex_class(entry: dict[str, Any]) -> re.Pattern[str]:
    flags = 0
    for name in entry.get("flags", []):
        flags |= REGEX_FLAG_NAMES.get(name, 0)
    return re.compile(entry["pattern"], flags)


@dataclass
class SecretScanner:
    regex_classes: dict[str, re.Pattern[str]]
    scanners: dict[str, dict[str, Any]]
    anchor_patterns: dict[str, re.Pattern[str]]


def build_secret_scanner(patterns: dict[str, Any]) -> SecretScanner:
    regex_classes: dict[str, re.Pattern[str]] = {}
    scanners: dict[str, dict[str, Any]] = {}
    anchors: dict[str, re.Pattern[str]] = {}
    for name, entry in patterns.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == "regex":
            regex_classes[name] = compile_regex_class(entry)
        elif entry.get("type") == "multi_line_scanner":
            scanners[name] = entry
            anchors[name] = re.compile(entry["anchor_regex"], re.MULTILINE)
    return SecretScanner(regex_classes=regex_classes, scanners=scanners, anchor_patterns=anchors)


def record_scanning_surface(record: dict[str, Any]) -> str:
    """Per §13: command + newline + each artifacts entry on its own line."""
    parts: list[str] = [str(record.get("command", ""))]
    artifacts = record.get("artifacts") or []
    if isinstance(artifacts, list):
        for artifact in artifacts:
            parts.append(str(artifact))
    return "\n".join(parts) + "\n"


def scan_secrets_in_records(
    scanner: SecretScanner,
    records: list[tuple[int, dict[str, Any], str]],
) -> list[tuple[int, str, str]]:
    """Returns list of (line_number, class_name, message).

    Each tuple represents one violation. Multi-line scanner attribution rules
    follow §13: violation belongs to the first record in the window whose
    surface produced the secondary-class match; overlapping windows do not
    re-fire the same scanner against the same trigger record.
    """
    violations: list[tuple[int, str, str]] = []

    # Single-line regex pass per record.
    for line_no, _record, surface in records:
        for class_name, regex in scanner.regex_classes.items():
            if regex.search(surface):
                violations.append(
                    (line_no, class_name, f"matched secret class {class_name}")
                )

    # Multi-line scanner pass.
    for class_name, entry in scanner.scanners.items():
        window = max(2, int(entry.get("window_lines", 2)))
        min_matches = max(1, int(entry.get("min_matches_in_window", 1)))
        secondary_classes = entry.get("secondary_match_classes", [])
        anchor = scanner.anchor_patterns[class_name]
        attributed: set[int] = set()
        for start in range(len(records)):
            slice_ = records[start : start + window]
            if not slice_:
                break
            composite = "\n".join(item[2] for item in slice_)
            anchor_count = len(anchor.findall(composite))
            if anchor_count < min_matches:
                continue
            trigger_line: int | None = None
            for line_no, _record, surface in slice_:
                if any(
                    secondary in scanner.regex_classes
                    and scanner.regex_classes[secondary].search(surface)
                    for secondary in secondary_classes
                ):
                    trigger_line = line_no
                    break
            if trigger_line is None or trigger_line in attributed:
                continue
            attributed.add(trigger_line)
            violations.append(
                (trigger_line, class_name, f"multi-line secret window matched {class_name}")
            )
    return violations


# --------------------------------------------------------------------------- #
# Output handling
# --------------------------------------------------------------------------- #


def output_result(result: Result, args: argparse.Namespace, exit_code: int) -> int:
    payload = result.to_json()
    json_text = json.dumps(payload, indent=2, sort_keys=False)
    if args.json_out:
        Path(args.json_out).write_text(json_text + "\n", encoding="utf-8")
    if args.json:
        print(json_text)
    else:
        print_human(result)
    return exit_code


def invocation_failure(args: argparse.Namespace, product_root: Path, effective_date: date, rule_id: str, message: str) -> int:
    result = Result(stage=args.stage or "closeout", product_root=product_root, effective_date=effective_date)
    result.add_error(rule_id, message)
    payload = result.to_json()
    json_text = json.dumps(payload, indent=2, sort_keys=False)
    if getattr(args, "json", False):
        print(json_text)
    else:
        print_human(result)
    return 2


def print_human(result: Result) -> None:
    for finding in result.errors:
        print(f"ERROR {finding.rule_id}: {finding.message}")
    for finding in result.warnings:
        print(f"WARNING {finding.rule_id}: {finding.message}")
    for finding in result.info:
        print(f"INFO {finding.rule_id}: {finding.message}")
    if not result.errors and not result.warnings and not result.info:
        print("Feature evidence validation passed.")
    print(
        "Summary: "
        f"validated={result.features_validated}, "
        f"skipped_pre_contract_archived={result.features_skipped_pre_contract_archived}, "
        f"skipped_active_done_pre_contract={result.features_skipped_active_done_pre_contract}, "
        f"skipped_retired_abandoned={result.features_skipped_retired_abandoned}, "
        f"skipped_retired_superseded={result.features_skipped_retired_superseded}"
    )


# --------------------------------------------------------------------------- #
# Config resolution
# --------------------------------------------------------------------------- #


def resolve_product_root(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    if os.environ.get("NEBULA_PRODUCT_ROOT"):
        return Path(os.environ["NEBULA_PRODUCT_ROOT"]).expanduser().resolve()
    return (FRAMEWORK_ROOT / ".." / "nebula-insurance-crm").resolve()


def parse_effective_date(raw: str | None) -> date:
    if not raw:
        return DEFAULT_EFFECTIVE_DATE
    parsed = parse_iso_date(raw)
    if parsed is None:
        return date.min
    return parsed


def validate_secret_patterns(product_root: Path) -> tuple[str | None, dict[str, Any]]:
    framework_path = SCRIPT_DIR / "secret_patterns.json"
    framework_patterns, error = load_json_file(framework_path)
    if error or not isinstance(framework_patterns, dict):
        return "secret_patterns_unloadable_fails", {}

    product_patterns: dict[str, Any] = {}
    product_path = product_root / "planning-mds" / "operations" / "evidence" / "secret_patterns.json"
    if product_path.exists():
        loaded, product_error = load_json_file(product_path)
        if product_error or not isinstance(loaded, dict):
            return "secret_patterns_unloadable_fails", {}
        product_patterns = loaded
        if set(framework_patterns).intersection(product_patterns):
            return "secret_patterns_conflict_fails", {}

    merged = {**framework_patterns, **product_patterns}
    regex_classes = {
        name
        for name, config in merged.items()
        if isinstance(config, dict) and config.get("type") == "regex"
    }
    for config in merged.values():
        if not isinstance(config, dict) or config.get("type") not in {"regex", "multi_line_scanner"}:
            return "secret_patterns_unloadable_fails", {}
        if config.get("type") == "multi_line_scanner":
            for secondary in config.get("secondary_match_classes", []):
                if secondary not in regex_classes:
                    return "secret_patterns_invalid_secondary_class_fails", {}
    return None, merged


def parse_forced_booleans(value: str) -> set[str]:
    return set(
        re.findall(
            r"\b(runtime_bearing|deployment_config_changed|frontend_in_scope|security_sensitive_scope)\b",
            value,
        )
    )


def validate_path_class_extensions(product_root: Path) -> bool:
    readme = product_root / "planning-mds" / "operations" / "evidence" / "README.md"
    if not readme.exists():
        return True
    section = extract_section(safe_read(readme) or "", "Path Class Extensions")
    for row in parse_table(section):
        glob_value = strip_code(row.get("Path class (glob)", "") or row.get("Path Class (glob)", ""))
        forces = parse_forced_booleans(row.get("Forces", ""))
        if not glob_value or not forces:
            continue
        default_forces = DEFAULT_PATH_CLASSES.get(glob_value)
        if default_forces is not None and not forces.issuperset(default_forces):
            return False
    return True


# --------------------------------------------------------------------------- #
# Registry parsing + eligibility
# --------------------------------------------------------------------------- #


def load_registry(product_root: Path, result: Result) -> dict[str, RegistryRow]:
    registry_path = product_root / "planning-mds" / "features" / "REGISTRY.md"
    if not registry_path.exists():
        result.add_error("registry_missing_fails", "REGISTRY.md is absent from planning-mds/features", path=str(registry_path))
        return {}
    content = registry_path.read_text(encoding="utf-8")
    required_sections = ["Active Features", "Archived Features", "Retired Features"]
    missing = [heading for heading in required_sections if not extract_section(content, heading)]
    if missing:
        result.add_error(
            "registry_required_section_missing_fails",
            "REGISTRY.md is missing required section(s): " + ", ".join(missing),
            path=str(registry_path),
        )
    rows: dict[str, RegistryRow] = {}
    for section in ("Active Features", "Planned (Reserved IDs)", "Archived Features", "Retired Features"):
        for row in parse_table(extract_section(content, section)):
            feature_id = row.get("Feature ID", "").strip()
            if FEATURE_ID_RE.fullmatch(feature_id):
                rows[feature_id] = RegistryRow(section, feature_id, row)
    return rows


def evidence_operations_root(product_root: Path) -> Path:
    return product_root / "planning-mds" / "operations" / "evidence"


def evidence_runs_root(product_root: Path) -> Path:
    return evidence_operations_root(product_root) / "runs"


def feature_index_root_for(product_root: Path, row: RegistryRow) -> Path:
    return evidence_operations_root(product_root) / "features" / row.evidence_slug


def run_folder_for(product_root: Path, run_id: str) -> Path:
    return evidence_runs_root(product_root) / run_id


def feature_manifests(product_root: Path, feature_id: str) -> list[Path]:
    runs_root = evidence_runs_root(product_root)
    if not runs_root.exists():
        return []
    manifests: list[Path] = []
    for candidate in sorted(runs_root.iterdir()):
        if not candidate.is_dir() or not RUN_ID_RE.fullmatch(candidate.name):
            continue
        manifest_path = candidate / "evidence-manifest.json"
        if not manifest_path.exists():
            continue
        loaded, error = load_json_file(manifest_path)
        if error or not isinstance(loaded, dict):
            continue
        if str(loaded.get("feature_id", "")) == feature_id:
            manifests.append(manifest_path)
    return manifests


def feature_path_for(product_root: Path, row: RegistryRow) -> Path:
    return product_root / "planning-mds" / "features" / row.folder.rstrip("/")


def is_terminal_active(row: RegistryRow) -> bool:
    return row.status.strip().casefold() in TERMINAL_ACTIVE_STATES


def archived_date(row: RegistryRow) -> date | None:
    return parse_iso_date(row.raw.get("Archived Date", ""))


def evidence_reentry_date(row: RegistryRow) -> date | None:
    return parse_iso_date(row.raw.get("Evidence Reentry Date", ""))


def classify_retired(row: RegistryRow, result: Result) -> None:
    terminal_status = row.raw.get("Terminal Status", "").strip().casefold()
    if terminal_status == "abandoned":
        result.features_skipped_retired_abandoned += 1
    elif terminal_status == "superseded":
        result.features_skipped_retired_superseded += 1


def extract_closeout_review_date(feature_path: Path) -> date | None:
    parsed, _ = extract_closeout_review_date_with_shape(feature_path)
    return parsed


def extract_closeout_review_date_with_shape(feature_path: Path) -> tuple[date | None, str]:
    """Returns (parsed_date, shape) where shape is one of 'parseable',
    'malformed', 'absent'. 'malformed' means the row exists with a non-empty
    value that did not parse."""
    status_path = feature_path / "STATUS.md"
    if not status_path.exists():
        return None, "absent"
    content = safe_read(status_path)
    if content is None:
        return None, "absent"
    section = extract_section(content, "Closeout Summary")
    for row in parse_table(section):
        field_name = row.get("Field", "").strip().casefold()
        if field_name == "closeout review date":
            value = (row.get("Value", "") or "").strip()
            parsed = parse_iso_date(value) if value else None
            if parsed is not None:
                return parsed, "parseable"
            if value:
                return None, "malformed"
            return None, "absent"
    return None, "absent"


def emit_reopened_reentry_rule_if_missing(
    row: RegistryRow, product_root: Path, result: Result,
) -> None:
    """When an archived feature carries a post-contract `Evidence Reentry Date`
    and no canonical evidence package exists, fire
    `reopened_historical_missing_evidence_fails` so the cause is clear in
    operator output (it complements `post_contract_archived_missing_evidence_fails`).
    """
    feature_index_root = feature_index_root_for(product_root, row)
    if not feature_index_root.exists() or not (feature_index_root / "latest-run.json").exists():
        result.add_error(
            "reopened_historical_missing_evidence_fails",
            "Archived feature has Evidence Reentry Date on/after the effective date but no canonical evidence",
            feature=row.feature_id, path=str(feature_index_root),
        )


def emit_malformed_closeout_date_rule_if_missing(
    row: RegistryRow, product_root: Path, result: Result,
) -> None:
    """When an active Done feature's STATUS.md has a malformed closeout date,
    the feature stays governed; fire
    `active_done_pre_contract_malformed_date_requires_evidence_fails` only if
    canonical evidence is also missing, so operators see both the cause and
    the missing package together."""
    feature_index_root = feature_index_root_for(product_root, row)
    if not feature_index_root.exists() or not (feature_index_root / "latest-run.json").exists():
        result.add_error(
            "active_done_pre_contract_malformed_date_requires_evidence_fails",
            "Active Done feature has a malformed Closeout review date and no canonical evidence; date cannot qualify for the pre-contract skip",
            feature=row.feature_id, path=str(feature_index_root),
        )


def governed_rows(rows: dict[str, RegistryRow], product_root: Path, result: Result, effective_date: date) -> list[RegistryRow]:
    governed: list[RegistryRow] = []
    for row in rows.values():
        if row.section == "Retired Features":
            classify_retired(row, result)
            continue
        if row.section == "Archived Features":
            row_archived_date = archived_date(row)
            if row_archived_date is None:
                result.add_error("archived_missing_date_fails", "Archived feature is missing a parseable Archived Date", feature=row.feature_id)
                continue
            reentry = evidence_reentry_date(row)
            if row_archived_date < effective_date and (reentry is None or reentry < effective_date):
                result.features_skipped_pre_contract_archived += 1
                continue
            if row_archived_date < effective_date and reentry is not None and reentry >= effective_date:
                emit_reopened_reentry_rule_if_missing(row, product_root, result)
            governed.append(row)
            continue
        if row.section == "Active Features":
            if not is_terminal_active(row):
                continue
            closeout_date, shape = extract_closeout_review_date_with_shape(feature_path_for(product_root, row))
            if shape == "parseable" and closeout_date is not None and closeout_date < effective_date:
                result.features_skipped_active_done_pre_contract += 1
                result.add_warning(
                    "active_done_pre_contract_parseable_skip_warns",
                    "Active terminal feature has pre-contract Closeout review date; completion evidence skipped",
                    feature=row.feature_id,
                )
                continue
            if shape == "malformed":
                emit_malformed_closeout_date_rule_if_missing(row, product_root, result)
            governed.append(row)
    return governed


def relative_json_path(product_root: Path, value: str) -> Path:
    cleaned = strip_code(value).rstrip("/")
    return product_root / cleaned


# --------------------------------------------------------------------------- #
# Latest-run + run resolution
# --------------------------------------------------------------------------- #


@dataclass
class LatestRunResolution:
    run_id: str | None
    manifest_path: Path | None
    mismatch: bool = False
    unloadable: bool = False


def validate_latest_run(
    row: RegistryRow,
    result: Result,
    latest_path: Path,
    supplied_run_id: str | None,
    require_match_rule: str | None,
) -> LatestRunResolution:
    loaded, error = load_json_file(latest_path)
    if error or not isinstance(loaded, dict):
        result.add_error("latest_run_wrong_manifest_fails", "latest-run.json is missing or unparseable", feature=row.feature_id, path=str(latest_path))
        return LatestRunResolution(None, None, unloadable=True)
    latest_run_id = str(loaded.get("run_id", ""))
    if not RUN_ID_RE.fullmatch(latest_run_id):
        result.add_error("latest_run_wrong_manifest_fails", "latest-run.json run_id is malformed", feature=row.feature_id, path=str(latest_path))
        return LatestRunResolution(None, None, unloadable=True)
    if supplied_run_id and supplied_run_id != latest_run_id and require_match_rule:
        result.add_error(
            require_match_rule,
            f"--run-id {supplied_run_id} does not match latest-run.json run_id {latest_run_id}",
            feature=row.feature_id,
            run_id=supplied_run_id,
            path=str(latest_path),
        )
        return LatestRunResolution(latest_run_id, None, mismatch=True)
    manifest_value = str(loaded.get("manifest_path", ""))
    manifest_path = relative_json_path(result.product_root, manifest_value) if manifest_value else None
    if manifest_path is None or not manifest_path.exists():
        result.add_error("latest_run_wrong_manifest_fails", "latest-run.json manifest_path does not resolve", feature=row.feature_id, run_id=latest_run_id, path=str(latest_path))
        return LatestRunResolution(latest_run_id, None, unloadable=True)
    return LatestRunResolution(latest_run_id, manifest_path)


def resolve_run(row: RegistryRow, stage: str, run_id: str | None, result: Result) -> tuple[str | None, Path | None, bool]:
    root = feature_index_root_for(result.product_root, row)
    latest_path = root / "latest-run.json"
    if stage in {"G0", "G1", "G2", "G3", "G4", "G5"}:
        if not run_id:
            result.add_error("stage_without_run_id_before_g6_fails", f"{stage} validation requires --run-id", feature=row.feature_id)
            return None, None, False
        run_folder = run_folder_for(result.product_root, run_id)
        if not run_folder.exists():
            result.add_error("run_folder_not_found_fails", "Run folder does not exist", feature=row.feature_id, run_id=run_id, path=str(run_folder))
            return run_id, None, False
        return run_id, run_folder / "evidence-manifest.json", False

    if stage in {"G6", "G7"}:
        if run_id:
            if latest_path.exists():
                resolution = validate_latest_run(row, result, latest_path, run_id, "stage_g6_run_id_mismatch_with_latest_run_fails")
                if resolution.mismatch or resolution.unloadable:
                    return run_id, None, False
            run_folder = run_folder_for(result.product_root, run_id)
            if not run_folder.exists():
                result.add_error("run_folder_not_found_fails", "Run folder does not exist", feature=row.feature_id, run_id=run_id, path=str(run_folder))
                return run_id, None, False
            return run_id, run_folder / "evidence-manifest.json", False
        if not latest_path.exists():
            result.add_error("stage_g6_without_run_id_or_latest_run_fails", f"{stage} validation requires --run-id or latest-run.json", feature=row.feature_id, path=str(root))
            return None, None, False
        resolution = validate_latest_run(row, result, latest_path, None, None)
        return resolution.run_id, resolution.manifest_path, True

    if not latest_path.exists():
        if not root.exists() and row.section == "Archived Features":
            result.add_error("post_contract_archived_missing_evidence_fails", "Post-contract archived feature lacks canonical evidence", feature=row.feature_id, path=str(root))
        elif not root.exists() and row.section == "Active Features":
            result.add_error("active_done_post_contract_missing_evidence_fails", "Active Done/completed feature lacks canonical evidence", feature=row.feature_id, path=str(root))
        else:
            result.add_error("missing_latest_run_fails", "latest-run.json is required for closeout validation", feature=row.feature_id, path=str(latest_path))
        return None, None, True
    resolution = validate_latest_run(row, result, latest_path, run_id, "stage_g8_run_id_mismatch_fails")
    return resolution.run_id, resolution.manifest_path, True


# --------------------------------------------------------------------------- #
# Manifest deep validation
# --------------------------------------------------------------------------- #


def _is_repo_relative(value: str) -> tuple[bool, bool]:
    """Returns (absolute, traverses). Both False means safe relative path."""
    if not value:
        return False, False
    if value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value):
        return True, False
    parts = re.split(r"[\\/]+", value)
    return False, ".." in parts


def validate_manifest_deep(
    row: RegistryRow,
    run_id: str | None,
    manifest: dict[str, Any],
    manifest_path: Path,
    result: Result,
    stage: str,
) -> None:
    """Layered manifest schema validation. Phase 2a covers path safety,
    boolean presence, waiver shape, rerun_of/changed_paths shape, status
    transitions, and feature_state terminality at closeout."""
    feature_id = row.feature_id
    common = {"feature": feature_id, "run_id": run_id or None, "path": str(manifest_path)}

    # Booleans presence
    for boolean_field, rule_id in (
        ("runtime_bearing", "manifest_missing_runtime_boolean_fails"),
        ("deployment_config_changed", "manifest_missing_deploy_boolean_fails"),
        ("frontend_in_scope", "manifest_missing_frontend_boolean_fails"),
        ("security_sensitive_scope", "manifest_missing_security_boolean_fails"),
    ):
        if not isinstance(manifest.get(boolean_field), bool):
            result.add_error(rule_id, f"Manifest {boolean_field} must be a boolean", **common)

    # changed_paths presence + shape
    rerun_of = manifest.get("rerun_of")
    changed_paths = manifest.get("changed_paths")
    if not isinstance(changed_paths, list):
        result.add_error("manifest_missing_changed_paths_fails", "Manifest changed_paths is missing or not an array", **common)
    else:
        if not changed_paths and rerun_of is None:
            result.add_error(
                "manifest_empty_changed_paths_without_rerun_of_fails",
                "Manifest changed_paths is empty while rerun_of is null",
                **common,
            )
        for path_value in changed_paths:
            if not isinstance(path_value, str):
                result.add_error("manifest_missing_changed_paths_fails", "changed_paths entries must be strings", **common)
                continue
            absolute, traverses = _is_repo_relative(path_value)
            if absolute:
                result.add_error("manifest_changed_path_absolute_fails", f"changed_paths entry must not be absolute: {path_value!r}", **common)
            if traverses:
                result.add_error("manifest_changed_path_traversal_fails", f"changed_paths entry must not contain '..': {path_value!r}", **common)

    # scm shape
    scm = manifest.get("scm")
    if isinstance(scm, dict):
        diff_artifact = scm.get("diff_artifact", "")
        if isinstance(diff_artifact, str) and diff_artifact:
            resolution = resolve_artifact_reference(result.product_root, manifest_path.parent, diff_artifact)
            if (
                _contains_parent_reference(diff_artifact)
                or resolution.error_kind in {"scratch_artifact_fails", "unmappable_absolute_artifact_fails"}
                or resolution.is_url
            ):
                result.add_error(
                    "manifest_scm_diff_path_malformed_fails",
                    "scm.diff_artifact must be a run-folder-relative path with no '..' segments",
                    **common,
                )
        elif rerun_of is None and not diff_artifact:
            result.add_error(
                "manifest_scm_diff_missing_fails",
                "scm.diff_artifact is required for implementation-changing runs",
                **common,
            )
    else:
        result.add_error("manifest_scm_diff_missing_fails", "Manifest scm object is missing", **common)

    # files shape
    files = manifest.get("files")
    if isinstance(files, dict):
        for key, value in files.items():
            if not isinstance(value, str) or not value:
                continue
            resolution = resolve_artifact_reference(result.product_root, manifest_path.parent, value)
            if resolution.error_kind in {"scratch_artifact_fails", "unmappable_absolute_artifact_fails"}:
                result.add_error("manifest_file_path_absolute_fails", f"files[{key!r}] must not be absolute: {value!r}", **common)
            if _contains_parent_reference(value):
                result.add_error("manifest_file_path_traversal_fails", f"files[{key!r}] must not contain '..': {value!r}", **common)

    # waivers shape
    waivers = manifest.get("waivers")
    if isinstance(waivers, dict):
        pm_acceptances = _load_pm_acceptances(manifest_path.parent / "pm-closeout.md")
        accepted_identifiers = {entry.identifier for entry in pm_acceptances}
        for key in waivers.keys():
            if key in RECOGNIZED_WAIVER_KEYS:
                continue
            if key not in accepted_identifiers:
                result.add_error(
                    "manifest_unknown_waiver_key_without_pm_acceptance_fails",
                    f"Manifest waiver key {key!r} is not recognized and lacks a PM Acceptance Line",
                    **common,
                )

    # security_scans completeness (QE→Security handoff)
    # QE is Responsible for running the four scan classes and publishing raw
    # output under artifacts/security/; Security is Accountable for the verdict.
    # A Security PASS is only defensible when every class either ran with a
    # resolvable artifact or carries a complete in-line waiver. Gated on the
    # run's own contract_effective_date so earlier packages stay valid.
    manifest_effective = parse_iso_date(str(manifest.get("contract_effective_date", "")))
    if (
        manifest.get("security_sensitive_scope") is True
        and manifest_effective is not None
        and manifest_effective >= SECURITY_SCANS_EFFECTIVE_DATE
    ):
        scans = manifest.get("security_scans")
        if not isinstance(scans, dict):
            result.add_error(
                "security_scans_missing_fails",
                "security_sensitive_scope is true but manifest.security_scans is missing or not an object",
                **common,
            )
        else:
            for scan_class in REQUIRED_SECURITY_SCAN_CLASSES:
                entry = scans.get(scan_class)
                if not isinstance(entry, dict):
                    result.add_error(
                        "security_scan_class_missing_fails",
                        f"security_scans is missing required scan class {scan_class!r}",
                        **common,
                    )
                    continue
                if entry.get("ran") is True:
                    artifact = entry.get("artifact")
                    if not isinstance(artifact, str) or not artifact:
                        result.add_error(
                            "security_scan_unbacked_fails",
                            f"security_scans[{scan_class!r}] ran but declares no artifact path",
                            **common,
                        )
                        continue
                    resolution = validate_artifact_reference(
                        result,
                        result.product_root,
                        manifest_path.parent,
                        artifact,
                        f"security_scans[{scan_class!r}] artifact",
                        missing_rule_id="security_scan_unbacked_fails",
                        missing_message=f"security_scans[{scan_class!r}] artifact does not resolve under the run folder: {artifact!r}",
                        **common,
                    )
                    if resolution.error_kind in {"scratch_artifact_fails", "unmappable_absolute_artifact_fails"}:
                        result.add_error(
                            "security_scan_unbacked_fails",
                            f"security_scans[{scan_class!r}] artifact does not resolve under the run folder: {artifact!r}",
                            **common,
                        )
                elif not _is_complete_scan_waiver(entry.get("waiver")):
                    result.add_error(
                        "security_scan_unwaived_skip_fails",
                        f"security_scans[{scan_class!r}] did not run and lacks a complete waiver (reason, owner, approved_on)",
                        **common,
                    )

    # G7 architect knowledge-graph reconciliation (date-gated).
    # The architect binds the as-built source into the semantic graph at G7;
    # closeout requires the gate result to be present and passing. Gated on the
    # run's own contract_effective_date so earlier packages stay valid.
    if kg_reconciliation_required(manifest, stage):
        gate_results = manifest.get("gate_results")
        kg_gate = gate_results.get("kg_reconciliation") if isinstance(gate_results, dict) else None
        if not isinstance(kg_gate, dict):
            result.add_error(
                "kg_reconciliation_gate_missing_fails",
                "Manifest gate_results.kg_reconciliation is missing (G7 architect KG reconciliation is required at closeout)",
                **common,
            )
        else:
            kg_result = str(kg_gate.get("result", "")).strip().upper()
            if kg_result not in PASSING_PASS_RESULTS:
                result.add_error(
                    "kg_reconciliation_gate_not_passing_fails",
                    f"gate_results.kg_reconciliation.result must be passing ({sorted(PASSING_PASS_RESULTS)}), got {kg_gate.get('result')!r}",
                    **common,
                )

    # status / feature_state at closeout
    status = manifest.get("status")
    feature_state = (manifest.get("feature_state") or "").strip().casefold()
    if stage in {"G8", "closeout"} and status == "approved":
        if feature_state in {"draft", "in progress"}:
            result.add_error(
                "manifest_final_approved_with_non_terminal_state_fails",
                f"Final approved manifest cannot carry feature_state={manifest.get('feature_state')!r}",
                **common,
            )
        if feature_state in RETIRED_FEATURE_STATES:
            result.add_error(
                "manifest_retired_state_fails",
                f"Final approved manifest cannot carry retired feature_state={manifest.get('feature_state')!r}",
                **common,
            )

    # feature_path_at_closeout shape before final closeout
    closeout_path = manifest.get("feature_path_at_closeout")
    if "feature_path_at_closeout" not in manifest:
        result.add_error("manifest_closeout_path_missing_fails", "Manifest is missing feature_path_at_closeout key", **common)
    elif closeout_path is not None:
        if not isinstance(closeout_path, str):
            result.add_error("manifest_closeout_path_missing_fails", "feature_path_at_closeout must be a string or null", **common)
        else:
            absolute, traverses = _is_repo_relative(closeout_path)
            if absolute or traverses:
                result.add_error("manifest_closeout_path_missing_fails", f"feature_path_at_closeout must be a non-absolute repo-relative path: {closeout_path!r}", **common)
            elif not (
                closeout_path.startswith("planning-mds/features/")
                or closeout_path.startswith("planning-mds/features/archive/")
            ):
                result.add_error("manifest_closeout_path_missing_fails", f"feature_path_at_closeout must live under planning-mds/features[/archive]: {closeout_path!r}", **common)


def _is_complete_scan_waiver(waiver: Any) -> bool:
    """A scan-class waiver must name reason, owner, and approved_on so a skipped
    scanner is an auditable decision rather than a silent gap."""
    if not isinstance(waiver, dict):
        return False
    return all(
        isinstance(waiver.get(field), str) and waiver.get(field, "").strip()
        for field in ("reason", "owner", "approved_on")
    )


def _load_pm_acceptances(pm_closeout_path: Path) -> list[PmAcceptance]:
    content = safe_read(pm_closeout_path)
    if content is None:
        return []
    return parse_pm_acceptance_lines(content)


# --------------------------------------------------------------------------- #
# Artifact + heading checks
# --------------------------------------------------------------------------- #


def validate_required_artifacts(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    stage: str,
    result: Result,
) -> None:
    runtime_bearing = bool(manifest.get("runtime_bearing"))
    security_sensitive = bool(manifest.get("security_sensitive_scope"))
    required_roles = manifest.get("required_roles") or []
    security_required = security_sensitive or "Security Reviewer" in required_roles

    expected = stage_required_files(stage, runtime_bearing, security_required)
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None

    # G7 architect KG reconciliation artifact (date-gated; see
    # KG_RECONCILIATION_EFFECTIVE_DATE). Earlier packages stay exempt.
    if kg_reconciliation_required(manifest, stage):
        expected = expected + ["kg-reconciliation.md"]

    artifact_rule_map = {
        "g0-assembly-plan-validation.md": "missing_g0_fails",
        "g1-runtime-preflight.md": "runtime_true_missing_preflight_fails",
        "g2-self-review.md": "missing_g2_fails",
        "test-plan.md": "missing_test_plan_fails",
        "test-execution-report.md": "missing_test_execution_fails",
        "coverage-report.md": "missing_coverage_report_fails",
        "deployability-check.md": "missing_deployability_fails",
        "code-review-report.md": "missing_code_review_fails",
        "security-review-report.md": "security_required_missing_report_fails",
        "feature-action-execution.md": "missing_feature_action_execution_fails",
        "pm-closeout.md": "missing_pm_closeout_fails",
        "kg-reconciliation.md": "kg_reconciliation_artifact_missing_fails",
    }

    for filename in expected:
        if filename == "evidence-manifest.json":
            continue
        target = run_folder / filename
        if target.exists():
            continue
        rule_id = artifact_rule_map.get(filename, "manifest_file_path_missing_fails")
        result.add_error(rule_id, f"Required artifact {filename!r} is missing", feature=feature_id, run_id=run_id, path=str(target))

    # Heading-presence checks for files that do exist.
    for filename, headings in REQUIRED_HEADINGS.items():
        target = run_folder / filename
        if not target.exists():
            continue
        content = safe_read(target) or ""
        missing = headings_present(content, headings)
        if not missing:
            continue
        rule_id = {
            "README.md": "missing_readme_heading_fails",
            "action-context.md": "action_context_wrong_feature_fails",
            "artifact-trace.md": "artifact_trace_missing_global_ref_fails",
        }.get(filename)
        if rule_id is None:
            # role report heading missing → use the corresponding `missing_*` rule
            rule_id = {
                "g2-self-review.md": "missing_g2_fails",
                "signoff-ledger.md": "signoff_ledger_disagrees_fails",
                "pm-closeout.md": "missing_pm_closeout_fails",
            }.get(filename, "missing_readme_heading_fails")
        result.add_error(rule_id, f"{filename} is missing required heading(s): {', '.join(missing)}", feature=feature_id, run_id=run_id, path=str(target))

    # action-context.md must name the feature ID + run ID under Run Identity.
    action_context = run_folder / "action-context.md"
    if action_context.exists():
        content = safe_read(action_context) or ""
        identity_section = extract_section(content, "Run Identity")
        if identity_section and feature_id not in identity_section:
            result.add_error(
                "action_context_wrong_feature_fails",
                f"action-context.md Run Identity does not mention {feature_id}",
                feature=feature_id,
                run_id=run_id,
                path=str(action_context),
            )

    # Runtime-bearing omission cross-check (manifest.runtime_bearing=False vs file present)
    omissions = manifest.get("omissions") or []
    if isinstance(omissions, list):
        for omission in omissions:
            if not isinstance(omission, dict):
                continue
            artifact = omission.get("artifact")
            if artifact == RUNTIME_PREFLIGHT_FILE and runtime_bearing:
                result.add_error(
                    "runtime_preflight_omitted_when_runtime_true_fails",
                    "g1-runtime-preflight.md cannot be omitted when runtime_bearing=true",
                    feature=feature_id,
                    run_id=run_id,
                )
            if artifact == SECURITY_REVIEW_FILE and security_required:
                result.add_error(
                    "security_report_omitted_when_required_fails",
                    "security-review-report.md cannot be omitted when security is required",
                    feature=feature_id,
                    run_id=run_id,
                )


# --------------------------------------------------------------------------- #
# Gate-decisions + lifecycle-gates + commands.log
# --------------------------------------------------------------------------- #


def validate_gate_decisions(
    run_folder: Path,
    manifest: dict[str, Any],
    stage: str,
    row: RegistryRow,
    result: Result,
) -> None:
    path = run_folder / "gate-decisions.md"
    content = safe_read(path)
    if content is None:
        return
    section = extract_section(content, "Gate Decisions") or content
    rows = parse_table(section)
    present = {strip_code(entry.get("Gate", "")).upper() for entry in rows}
    required = STAGE_REQUIRED_GATES.get(stage, [])
    if not kg_reconciliation_required(manifest, stage):
        required = [gate for gate in required if gate != "G7"]
    missing = [gate for gate in required if gate.upper() not in present]
    if missing:
        result.add_error(
            "gate_decisions_missing_stage_required_row_fails",
            f"gate-decisions.md missing required gate row(s) for stage {stage}: {', '.join(missing)}",
            feature=row.feature_id,
            path=str(path),
        )
    if stage in {"G5", "G6", "G7", "G8", "closeout"} and "G5" not in present:
        result.add_error("gate_decisions_missing_g5_fails", "gate-decisions.md missing G5 row", feature=row.feature_id, path=str(path))
    if stage in {"G6", "G7", "G8", "closeout"} and "G6" not in present:
        result.add_error("gate_decisions_missing_g6_fails", "gate-decisions.md missing G6 row", feature=row.feature_id, path=str(path))
    if kg_reconciliation_required(manifest, stage) and "G7" not in present:
        result.add_error("gate_decisions_missing_g7_fails", "gate-decisions.md missing G7 row", feature=row.feature_id, path=str(path))
    if stage in {"G8", "closeout"} and "G8" not in present:
        result.add_error("gate_decisions_missing_g8_fails", "gate-decisions.md missing G8 row", feature=row.feature_id, path=str(path))


def validate_lifecycle_gates(run_folder: Path, row: RegistryRow, result: Result) -> None:
    path = run_folder / "lifecycle-gates.log"
    content = safe_read(path)
    if content is None:
        return
    headings = collect_headings(content)
    missing = [
        heading
        for heading in ("Lifecycle Gate Run", "Command", "Stage", "Exit Code", "Result", "Output References", "Skipped Gates")
        if normalize_heading(heading) not in headings
    ]
    body_text = content.lower()
    if "exit code" not in body_text and "exit code" not in {h.lower() for h in headings} and missing:
        # Only fire when none of the headings nor inline mentions of exit code exist.
        result.add_error(
            "lifecycle_gates_missing_exit_code_fails",
            "lifecycle-gates.log is missing the Exit Code structure",
            feature=row.feature_id,
            path=str(path),
        )


def validate_commands_log(
    run_folder: Path,
    manifest: dict[str, Any],
    secret_scanner: SecretScanner,
    row: RegistryRow,
    result: Result,
) -> None:
    path = run_folder / "commands.log"
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    parsed_records: list[tuple[int, dict[str, Any], str]] = []
    non_empty_lines = 0
    has_absolute_cwd = False
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        non_empty_lines += 1
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            result.add_error(
                "commands_log_malformed_json_fails",
                f"commands.log line {line_no} is not valid JSON",
                feature=feature_id,
                run_id=run_id,
                path=str(path),
            )
            continue
        if not isinstance(record, dict):
            result.add_error(
                "commands_log_malformed_json_fails",
                f"commands.log line {line_no} is not a JSON object",
                feature=feature_id,
                run_id=run_id,
                path=str(path),
            )
            continue
        if not isinstance(record.get("exit_code"), int):
            result.add_error(
                "commands_log_missing_exit_code_fails",
                f"commands.log line {line_no} is missing an integer exit_code",
                feature=feature_id,
                run_id=run_id,
                path=str(path),
            )
        cwd_value = str(record.get("cwd", ""))
        if cwd_value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", cwd_value):
            has_absolute_cwd = True
        artifacts = record.get("artifacts") or []
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if not isinstance(artifact, str):
                    continue
                if not artifact:
                    continue
                validate_artifact_reference(
                    result,
                    result.product_root,
                    run_folder,
                    artifact,
                    f"commands.log line {line_no} artifact",
                    missing_rule_id="commands_log_artifact_missing_fails",
                    missing_message=f"commands.log line {line_no} references missing artifact {artifact!r}",
                    feature=feature_id,
                    run_id=run_id,
                    path=str(path),
                )
        parsed_records.append((line_no, record, record_scanning_surface(record)))

    status = manifest.get("status")
    if status == "approved" and non_empty_lines == 0:
        result.add_error(
            "commands_log_empty_at_approved_fails",
            "commands.log has zero non-empty lines while manifest status is approved",
            feature=feature_id,
            run_id=run_id,
            path=str(path),
        )

    if has_absolute_cwd and not _absolute_cwd_justified(run_folder):
        result.add_warning(
            "commands_log_absolute_cwd_warns",
            "commands.log contains an absolute cwd without Run Environment justification",
            feature=feature_id,
            run_id=run_id,
            path=str(path),
        )

    # Secret scanning.
    for line_no, class_name, message in scan_secrets_in_records(secret_scanner, parsed_records):
        result.add_error(
            "commands_log_secret_pattern_fails",
            f"commands.log line {line_no} {message}",
            feature=feature_id,
            run_id=run_id,
            path=str(path),
        )


# --------------------------------------------------------------------------- #
# §15 Recommendation + waiver acceptance validation
# --------------------------------------------------------------------------- #


# Role reports that can yield WITH RECOMMENDATIONS verdicts.
RECOMMENDATION_BEARING_REPORTS = [
    "g0-assembly-plan-validation.md",
    "g1-runtime-preflight.md",
    "g2-self-review.md",
    "test-plan.md",
    "test-execution-report.md",
    "coverage-report.md",
    "deployability-check.md",
    "code-review-report.md",
    "security-review-report.md",
    "signoff-ledger.md",
]


def _pm_acceptance_for(acceptances: list[PmAcceptance], identifier: str) -> PmAcceptance | None:
    """Case-insensitive lookup of a PM acceptance line by identifier."""
    needle = identifier.strip().casefold()
    for entry in acceptances:
        if entry.identifier.strip().casefold() == needle:
            return entry
    # Fall back: identifier appears as a substring (recommendation text)
    for entry in acceptances:
        if needle and needle in entry.identifier.strip().casefold():
            return entry
    return None


def validate_recommendations_in_role_reports(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    stage: str,
    result: Result,
) -> None:
    """§15 recommendation structure + PM acceptance.

    For every role report that yielded a `WITH RECOMMENDATIONS` verdict, parse
    its recommendation bullets and emit:
    - `recommendation_missing_severity_fails` if severity tag absent or invalid
    - `recommendation_missing_owner_fails` if owner/follow-up disposition absent
    - `recommendation_ambiguous_fails` for malformed recommendation lines
    - `blocking_language_with_pass_fails` for `high`/`critical` without PM mitigation
    - `recommendation_no_pm_acceptance_fails` when a deferred recommendation
      has no matching PM Acceptance Line (per §15)
    """
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    pm_closeout_path = run_folder / "pm-closeout.md"
    acceptances: list[PmAcceptance] = parse_pm_acceptance_lines(safe_read(pm_closeout_path) or "")

    for filename in RECOMMENDATION_BEARING_REPORTS:
        report_path = run_folder / filename
        content = safe_read(report_path)
        if content is None:
            continue
        verdict = (extract_verdict(content) or "").upper()
        if "WITH RECOMMENDATIONS" not in verdict:
            continue
        common = {"feature": feature_id, "run_id": run_id, "path": str(report_path)}
        recs = parse_recommendations(content)
        if not recs:
            # WITH RECOMMENDATIONS verdict but no parseable recommendations is
            # itself ambiguous — fire once per report.
            result.add_error(
                "recommendation_ambiguous_fails",
                f"{filename} verdict is {verdict!r} but no recommendation bullets parse",
                **common,
            )
            continue

        for rec in recs:
            if rec.severity is None or rec.severity not in SEVERITY_VALUES:
                kind = "missing" if rec.severity is None else f"invalid ({rec.severity_raw!r})"
                result.add_error(
                    "recommendation_missing_severity_fails",
                    f"Recommendation in {filename} has {kind} severity: {rec.raw!r}",
                    **common,
                )
                # If severity is malformed we still continue: owner/disposition is independent.
            if not rec.has_disposition:
                result.add_error(
                    "recommendation_missing_owner_fails",
                    f"Recommendation in {filename} missing owner/follow-up disposition: {rec.raw!r}",
                    **common,
                )
                # Without disposition we cannot determine "non-blocking" intent.
                result.add_error(
                    "recommendation_ambiguous_fails",
                    f"Recommendation in {filename} is ambiguous (no disposition): {rec.raw!r}",
                    **common,
                )
                continue

            if stage not in {"G8", "closeout"}:
                # Recommendations only require PM acceptance at closeout.
                continue

            acceptance = _pm_acceptance_for(acceptances, rec.text)
            if rec.severity in BLOCKING_SEVERITIES:
                if acceptance is None or "mitigation:" not in acceptance.details.casefold():
                    result.add_error(
                        "blocking_language_with_pass_fails",
                        f"{rec.severity}-severity recommendation in {filename} requires explicit PM mitigation acceptance: {rec.raw!r}",
                        **common,
                    )
                continue
            if acceptance is None:
                result.add_error(
                    "recommendation_no_pm_acceptance_fails",
                    f"Recommendation in {filename} has no matching PM Acceptance Line: {rec.raw!r}",
                    **common,
                )


def validate_coverage_waiver_acceptance(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    stage: str,
    result: Result,
) -> None:
    """§18 coverage waiver — must be mirrored in pm-closeout.md PM Acceptance Lines at closeout."""
    waivers = manifest.get("waivers")
    if not isinstance(waivers, dict):
        return
    coverage_waiver = waivers.get("coverage")
    if not isinstance(coverage_waiver, dict):
        return
    if stage not in {"G6", "G8", "closeout"}:
        return
    pm_closeout_path = run_folder / "pm-closeout.md"
    acceptances = parse_pm_acceptance_lines(safe_read(pm_closeout_path) or "")
    if _pm_acceptance_for(acceptances, "coverage") is None:
        result.add_error(
            "coverage_waiver_missing_pm_acceptance_fails",
            "Coverage waiver in manifest lacks a matching PM Acceptance Line (per §15 PM Acceptance Line Format) in pm-closeout.md",
            feature=row.feature_id,
            run_id=manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None,
            path=str(pm_closeout_path),
        )


def validate_validator_defect_waiver(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    stage: str,
    result: Result,
) -> None:
    """§11 + §22 — validator_defect waiver shape + pm-closeout.md mirror."""
    waivers = manifest.get("waivers")
    if not isinstance(waivers, dict):
        return
    defect = waivers.get("validator_defect")
    if not isinstance(defect, dict):
        return
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    common = {"feature": feature_id, "run_id": run_id, "path": str(run_folder / "evidence-manifest.json")}

    # Required fields per §11
    required_fields = ["defect_description", "affected_rule_ids", "approved_by", "approved_on", "follow_up_owner", "follow_up_target_date"]
    missing_fields = [field_name for field_name in required_fields if field_name not in defect]
    if missing_fields:
        result.add_error(
            "validator_defect_waiver_missing_followup_fails",
            f"validator_defect waiver is missing field(s): {missing_fields!r}",
            **common,
        )
        return

    affected_rule_ids = defect.get("affected_rule_ids")
    if not isinstance(affected_rule_ids, list) or not affected_rule_ids:
        result.add_error(
            "validator_defect_waiver_missing_followup_fails",
            "validator_defect waiver.affected_rule_ids must be a non-empty array",
            **common,
        )
        return

    # Dates must be parseable ISO + target on/after recorded_on
    target_date = parse_iso_date(str(defect.get("follow_up_target_date", "")))
    if target_date is None:
        result.add_error(
            "validator_defect_waiver_missing_followup_fails",
            "validator_defect waiver.follow_up_target_date must be a parseable ISO date",
            **common,
        )
        return
    recorded_on = parse_iso_date(str(manifest.get("recorded_on", "")))
    if recorded_on and target_date < recorded_on:
        result.add_error(
            "validator_defect_waiver_missing_followup_fails",
            f"validator_defect waiver.follow_up_target_date {target_date.isoformat()} is before manifest.recorded_on {recorded_on.isoformat()}",
            **common,
        )
        return

    if stage not in {"G6", "G8", "closeout"}:
        return

    pm_closeout = run_folder / "pm-closeout.md"
    pm_content = safe_read(pm_closeout) or ""
    acceptances = parse_pm_acceptance_lines(pm_content)
    for rule_id in affected_rule_ids:
        rule_id_str = str(rule_id)
        if _pm_acceptance_for(acceptances, rule_id_str) is None:
            result.add_error(
                "validator_defect_waiver_missing_followup_fails",
                f"validator_defect waiver covers rule {rule_id_str!r} but no matching PM Acceptance Line found in pm-closeout.md",
                feature=feature_id,
                run_id=run_id,
                path=str(pm_closeout),
            )


# --------------------------------------------------------------------------- #
# §16 STATUS.md signoff parsing
# --------------------------------------------------------------------------- #


STATUS_REQUIRED_COLUMNS = ["Story", "Role", "Reviewer", "Verdict", "Evidence", "Date", "Notes"]
STORY_REF_RE = re.compile(r"^F\d{4}-S\d{4}$")


def _find_signoff_table(content: str) -> str:
    """Look for the canonical signoff table — try common heading variants."""
    for heading in (
        "Story Signoff Provenance",
        "Story Signoff",
        "Signoff Provenance",
        "Signoff",
        "Signoff State",
        "Current Signoff State",
    ):
        section = extract_section(content, heading)
        if section and "| Story" in section and "| Role" in section:
            return section
    # Fall back: scan the whole document for a table with the required header.
    for match in re.finditer(r"(\|\s*Story\s*\|.+?\n(\|.*\n)+)", content):
        block = match.group(1)
        if all(col in block for col in ("Role", "Reviewer", "Verdict")):
            return block
    return ""


def parse_status_required_roles(row: RegistryRow, result: Result) -> set[str]:
    """Best-effort parse of the STATUS.md `Required Role Matrix`."""
    status_path = feature_path_for(result.product_root, row) / "STATUS.md"
    content = safe_read(status_path)
    if content is None:
        return set()
    section = extract_section(content, "Required Role Matrix")
    if not section:
        return set()
    roles: set[str] = set()
    for entry in parse_table(section):
        role_name = strip_code(entry.get("Role", ""))
        required_field = strip_code(entry.get("Required", "")).casefold()
        if role_name and required_field in {"yes", "true", "required", "y"}:
            roles.add(role_name)
    return roles


def validate_status_md(row: RegistryRow, manifest: dict[str, Any], run_folder: Path, stage: str, result: Result) -> None:
    """Validate the STATUS.md signoff provenance per §16."""
    status_path = feature_path_for(result.product_root, row) / "STATUS.md"
    content = safe_read(status_path)
    if content is None:
        # STATUS.md absence is not its own rule here — the validate_required_artifacts
        # rules above already flag missing role reports.
        return

    section = _find_signoff_table(content)
    if not section:
        return
    rows_raw = parse_table(section)
    if not rows_raw:
        return

    # Each row will be indexed by lowercased column name for tolerance.
    canonical_rows: list[dict[str, str]] = []
    for entry in rows_raw:
        lower = {key.strip().casefold(): value for key, value in entry.items()}
        canonical_rows.append(lower)

    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    common = {"feature": feature_id, "run_id": run_id, "path": str(status_path)}

    # Latest-row-per-(story, role).
    current: dict[tuple[str, str], dict[str, str]] = {}
    for entry in canonical_rows:
        story = strip_code(entry.get("story", ""))
        role = strip_code(entry.get("role", ""))
        if not story or not role:
            continue
        current[(story, role)] = entry

    canonical_run_root = run_folder
    runtime_bearing = bool(manifest.get("runtime_bearing"))
    security_required = bool(manifest.get("security_sensitive_scope"))
    deployment_changed = bool(manifest.get("deployment_config_changed"))

    status_required = parse_status_required_roles(row, result)
    effective_roles = effective_required_roles(manifest, status_required)

    # Local story breakdown (story files under the feature folder) — used by
    # `status_story_value_unknown_story_fails`. Source-of-truth per §16.
    feature_path = feature_path_for(result.product_root, row)
    local_story_ids: set[str] = set()
    if feature_path.exists():
        for child in feature_path.rglob("*.md"):
            stem = child.stem
            # Story file naming convention: F####-S####-...
            match = re.match(r"^(F\d{4}-S\d{4})", stem)
            if match:
                local_story_ids.add(match.group(1))

    # PM acceptances for status_recommendation_without_acceptance_fails
    pm_acceptances = parse_pm_acceptance_lines(safe_read(run_folder / "pm-closeout.md") or "")

    # Validate per-row content.
    stories_seen: set[str] = set()
    for (story, role), entry in current.items():
        stories_seen.add(story)
        if not STORY_REF_RE.fullmatch(story):
            result.add_error(
                "status_story_value_bad_format_fails",
                f"STATUS.md story value {story!r} does not match F####-S####",
                **common,
            )
            continue

        if local_story_ids and story not in local_story_ids:
            result.add_error(
                "status_story_value_unknown_story_fails",
                f"STATUS.md story {story!r} is not present in the feature's local story breakdown",
                **common,
            )

        verdict = strip_code(entry.get("verdict", ""))
        if "WITH RECOMMENDATIONS" in verdict.upper() and stage in {"G8", "closeout"}:
            # Look for a PM acceptance whose identifier matches this story/role.
            matched = False
            for needle in (f"{story}-{role}", story, role):
                if _pm_acceptance_for(pm_acceptances, needle):
                    matched = True
                    break
            if not matched:
                result.add_error(
                    "status_recommendation_without_acceptance_fails",
                    f"STATUS.md row ({story}, {role}) is WITH RECOMMENDATIONS but lacks a matching PM Acceptance Line",
                    **common,
                )
        is_passing = verdict.upper() in {v.upper() for v in ROLE_PASSING_REVIEWS}
        if is_passing:
            reviewer = strip_code(entry.get("reviewer", ""))
            if not reviewer:
                result.add_error(
                    "status_missing_reviewer_fails",
                    f"STATUS.md row ({story}, {role}) is missing reviewer",
                    **common,
                )
            date_value = strip_code(entry.get("date", ""))
            if parse_iso_date(date_value) is None:
                result.add_error(
                    "status_bad_date_fails",
                    f"STATUS.md row ({story}, {role}) has non-ISO date {date_value!r}",
                    **common,
                )
            evidence_value = strip_code(entry.get("evidence", ""))
            if evidence_value:
                expected_prefix = canonical_run_root
                resolution = validate_artifact_reference(
                    result,
                    result.product_root,
                    canonical_run_root,
                    evidence_value,
                    f"STATUS.md row ({story}, {role}) evidence path",
                    generic_missing=False,
                    **common,
                )
                resolved = resolution.normalized_path
                if not resolution.exists or resolved is None:
                    result.add_error(
                        "status_evidence_missing_file_fails",
                        f"STATUS.md row ({story}, {role}) evidence path {evidence_value!r} does not resolve",
                        **common,
                    )
                else:
                    try:
                        resolved.resolve().relative_to(expected_prefix.resolve())
                    except ValueError:
                        # Allow global lanes (frontend-quality/frontend-ux) — referenced by
                        # the §20 contract — and the feature's STATUS folder itself.
                        evidence_under = "planning-mds/operations/evidence/"
                        if evidence_under in str(resolved) and not any(
                            lane in str(resolved) for lane in ("frontend-quality", "frontend-ux")
                        ):
                            result.add_error(
                                "status_evidence_outside_package_fails",
                                f"STATUS.md row ({story}, {role}) evidence {evidence_value!r} is not under the canonical run folder",
                                **common,
                            )

    # Baseline + forced roles
    if stage in {"G5", "G6", "G7", "G8", "closeout"}:
        all_required = {"Quality Engineer", "Code Reviewer"}
        if security_required:
            all_required.add("Security Reviewer")
        if deployment_changed:
            all_required.add("DevOps")

        for required_role in all_required - status_required:
            if required_role in {"Quality Engineer", "Code Reviewer"}:
                result.add_error(
                    "status_missing_baseline_role_fails",
                    f"STATUS.md Required Role Matrix does not require baseline role {required_role!r}",
                    **common,
                )
            else:
                result.add_error(
                    "status_missing_forced_role_fails",
                    f"STATUS.md Required Role Matrix does not require forced role {required_role!r}",
                    **common,
                )

        # Each story present in current must have a current passing row for every effective role.
        for story in stories_seen:
            for required_role in effective_roles:
                entry = current.get((story, required_role))
                if entry is None:
                    result.add_error(
                        "status_story_missing_role_fails",
                        f"Story {story!r} has no current signoff row for required role {required_role!r}",
                        **common,
                    )
                    continue
                verdict_value = strip_code(entry.get("verdict", ""))
                if verdict_value.upper() not in {v.upper() for v in ROLE_PASSING_REVIEWS}:
                    result.add_error(
                        "status_stale_pass_followed_by_fail_fails",
                        f"Story {story!r} role {required_role!r} latest verdict {verdict_value!r} is not passing",
                        **common,
                    )

    # signoff_ledger_stale_fails is now enforced by §21 cross-artifact consistency
    # (validate_signoff_ledger_consistency). The Phase 2a warning version is
    # superseded; no duplicate check here.


def validate_role_and_gate_results(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    stage: str,
    result: Result,
    status_required: set[str],
) -> None:
    """§11 + §14 — deep verdict reconciliation.

    Validates manifest.gate_results, manifest.role_results, manifest.required_roles,
    manifest.files, manifest.omissions, and manifest.global_evidence_refs. Each rule
    is keyed to the stage at which the underlying gate/role becomes required, so
    earlier stages don't fire on artifacts that legitimately have not landed yet.
    """
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    common = {"feature": feature_id, "run_id": run_id, "path": str(run_folder)}

    runtime_bearing = bool(manifest.get("runtime_bearing"))

    # gate_results shape + verdicts
    gate_results = manifest.get("gate_results")
    if not isinstance(gate_results, dict):
        result.add_error("manifest_missing_gate_results_fails", "Manifest gate_results must be an object", **common)
        gate_results = {}
    for key, spec in GATE_SPEC.items():
        if key == "kg_reconciliation" and not kg_reconciliation_required(manifest, stage):
            continue
        if not gate_required_at_stage(key, stage, runtime_bearing):
            continue
        entry = gate_results.get(key)
        if not isinstance(entry, dict):
            result.add_error(
                "manifest_missing_gate_results_fails",
                f"Manifest gate_results.{key} is missing or not an object",
                **common,
            )
            continue
        if entry.get("required") is not True:
            result.add_error(
                "manifest_missing_gate_results_fails",
                f"Manifest gate_results.{key}.required must be true at stage {stage}",
                **common,
            )
        verdict = entry.get("result")
        if not isinstance(verdict, str) or verdict.strip() not in spec["passing"]:
            result.add_error(
                "gate_verdict_mismatch_fails",
                f"Manifest gate_results.{key}.result={verdict!r} is not a passing verdict at stage {stage}",
                **common,
            )
        artifact_value = entry.get("artifact")
        if isinstance(artifact_value, str) and artifact_value:
            validate_artifact_reference(
                result,
                result.product_root,
                run_folder,
                artifact_value,
                f"gate_results.{key}.artifact",
                missing_rule_id="manifest_file_path_missing_fails",
                missing_message=f"gate_results.{key}.artifact does not resolve: {artifact_value!r}",
                **common,
            )

    # role_results shape + verdicts
    role_results = manifest.get("role_results")
    if not isinstance(role_results, dict):
        result.add_error("manifest_role_results_mismatch_fails", "Manifest role_results must be an object", **common)
        role_results = {}
    effective = effective_required_roles(manifest, status_required)
    for role_name, spec in ROLE_SPEC.items():
        if not role_required_at_stage(role_name, stage, manifest, status_required):
            continue
        entry = role_results.get(role_name)
        if not isinstance(entry, dict):
            result.add_error(
                "manifest_role_results_mismatch_fails",
                f"Manifest role_results[{role_name!r}] is missing or not an object at stage {stage}",
                **common,
            )
            continue
        if entry.get("required") is not True:
            result.add_error(
                "manifest_role_results_mismatch_fails",
                f"role_results[{role_name!r}].required must be true",
                **common,
            )
        verdict = entry.get("result")
        if not isinstance(verdict, str) or verdict.strip() not in spec["passing"]:
            result.add_error(
                "role_verdict_mismatch_fails",
                f"role_results[{role_name!r}].result={verdict!r} is not a passing verdict for {role_name}",
                **common,
            )
        required_artifacts = entry.get("required_artifacts")
        expected_artifacts = list(spec["required_artifacts"])
        if role_name == "DevOps" and runtime_bearing:
            expected_artifacts = ["g1-runtime-preflight.md"] + expected_artifacts
        if not isinstance(required_artifacts, list) or set(expected_artifacts) - set(required_artifacts):
            result.add_error(
                "manifest_role_results_mismatch_fails",
                f"role_results[{role_name!r}].required_artifacts must include {expected_artifacts!r}",
                **common,
            )
        verdict_artifact = entry.get("verdict_artifact")
        if verdict_artifact and isinstance(verdict_artifact, str):
            validate_artifact_reference(
                result,
                result.product_root,
                run_folder,
                verdict_artifact,
                f"role_results[{role_name!r}].verdict_artifact",
                missing_rule_id="manifest_file_path_missing_fails",
                missing_message=f"role_results[{role_name!r}].verdict_artifact does not resolve: {verdict_artifact!r}",
                **common,
            )

    # required_roles array
    declared_roles = manifest.get("required_roles")
    if isinstance(declared_roles, list):
        declared_set = {str(item) for item in declared_roles}
        missing_in_declared = effective - declared_set
        if missing_in_declared:
            result.add_error(
                "manifest_required_roles_mismatch_fails",
                f"Manifest required_roles is missing forced roles: {sorted(missing_in_declared)!r}",
                **common,
            )
            # §21 short-form rule that names the same condition cross-artifact.
            result.add_error(
                "required_roles_mismatch_fails",
                f"Manifest required_roles disagrees with effective forced-role set: missing {sorted(missing_in_declared)!r}",
                **common,
            )

    # files dict — every value must resolve
    files = manifest.get("files")
    if isinstance(files, dict):
        for key, value in files.items():
            if not isinstance(value, str) or not value:
                continue
            if _contains_parent_reference(value):
                continue  # already covered by manifest_file_path_traversal_fails
            validate_artifact_reference(
                result,
                result.product_root,
                run_folder,
                value,
                f"Manifest files[{key!r}]",
                missing_rule_id="manifest_file_path_missing_fails",
                missing_message=f"Manifest files[{key!r}]={value!r} does not exist",
                **common,
            )

    # omissions — must not reference required role/gate artifacts
    omissions = manifest.get("omissions") or []
    if isinstance(omissions, list):
        required_artifacts: set[str] = set()
        for role_name, spec in ROLE_SPEC.items():
            if role_required_at_stage(role_name, stage, manifest, status_required):
                required_artifacts.update(spec["required_artifacts"])
        for key, gate_spec in GATE_SPEC.items():
            if key == "kg_reconciliation" and not kg_reconciliation_required(manifest, stage):
                continue
            if gate_required_at_stage(key, stage, runtime_bearing):
                required_artifacts.add(gate_spec["artifact"])
        for omission in omissions:
            if not isinstance(omission, dict):
                continue
            artifact_name = omission.get("artifact")
            if artifact_name in required_artifacts:
                result.add_error(
                    "manifest_required_artifact_omitted_fails",
                    f"Required artifact {artifact_name!r} cannot appear in omissions[]",
                    **common,
                )
                # §18 short-form rule. Both names cite the same condition; emit
                # both so the §23 inventory rule_id is also discoverable in
                # downstream tooling.
                result.add_error(
                    "required_artifact_omitted_fails",
                    f"Required artifact {artifact_name!r} cannot appear in omissions[]",
                    **common,
                )

    # global_evidence_refs — every cited path must resolve
    global_refs = manifest.get("global_evidence_refs")
    if isinstance(global_refs, dict):
        for key, value in global_refs.items():
            candidates: list[str] = []
            if isinstance(value, str):
                candidates = [value]
            elif isinstance(value, list):
                candidates = [str(item) for item in value if isinstance(item, str)]
            for path_value in candidates:
                validate_artifact_reference(
                    result,
                    result.product_root,
                    run_folder,
                    path_value,
                    f"global_evidence_refs[{key!r}]",
                    missing_rule_id="manifest_global_ref_missing_fails",
                    missing_message=f"global_evidence_refs[{key!r}] does not resolve: {path_value!r}",
                    **common,
                )

    # waiver-mirror checks
    waivers = manifest.get("waivers")
    if isinstance(waivers, dict):
        coverage_waiver = waivers.get("coverage")
        if isinstance(coverage_waiver, dict):
            coverage_report = run_folder / "coverage-report.md"
            content = safe_read(coverage_report) or ""
            if not re.search(r"\bwaive", content, re.IGNORECASE):
                result.add_error(
                    "manifest_waiver_without_report_fails",
                    "coverage waiver in manifest is not mirrored in coverage-report.md",
                    **common,
                )


# --------------------------------------------------------------------------- #
# §7 + §21 SCM diff + path-class boolean reconciliation
# --------------------------------------------------------------------------- #


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """Compile a `**`-aware glob to a case-sensitive regex (§7)."""
    parts: list[str] = []
    i = 0
    while i < len(glob):
        if glob[i : i + 2] == "**":
            parts.append(".*")
            i += 2
        elif glob[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(glob[i]))
            i += 1
    return re.compile("^" + "".join(parts) + "$")


def _matches_glob(path: str, glob: str) -> bool:
    return bool(_glob_to_regex(glob).fullmatch(path))


def forced_booleans_for_paths(paths: Iterable[str]) -> set[str]:
    """Return the union of forced booleans across the given paths per §7."""
    forced: set[str] = set()
    for path_value in paths:
        for glob, booleans in DEFAULT_PATH_CLASSES.items():
            if _matches_glob(path_value, glob):
                forced |= booleans
    return forced


def validate_scope_booleans_against_paths(
    row: RegistryRow,
    manifest: dict[str, Any],
    result: Result,
    manifest_path: Path,
) -> None:
    """§7 + §21 — manifest path-class changes must force the matching booleans."""
    changed_paths = manifest.get("changed_paths") or []
    if not isinstance(changed_paths, list):
        return
    forced = forced_booleans_for_paths(str(p) for p in changed_paths if isinstance(p, str))
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    common = {"feature": feature_id, "run_id": run_id, "path": str(manifest_path)}
    for boolean_name in forced:
        if manifest.get(boolean_name) is False:
            result.add_error(
                "scope_boolean_false_with_changed_paths_fails",
                f"Manifest {boolean_name}=false contradicts changed_paths matching a §7 path class",
                **common,
            )


def parse_scm_diff_file(diff_path: Path) -> tuple[list[str], str | None]:
    """Parse a git diff --name-only style file. Returns (paths, error_msg)."""
    if not diff_path.exists():
        return [], "missing"
    try:
        text = diff_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], f"read error: {exc}"
    paths: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        paths.append(cleaned)
    return paths, None


def _is_covered_by(diff_path: str, manifest_paths: list[str]) -> bool:
    """A diff path is covered if it equals or is under any manifest changed-path entry."""
    normalized_diff = diff_path.strip().rstrip("/")
    for candidate in manifest_paths:
        norm_candidate = candidate.strip().rstrip("/")
        if not norm_candidate:
            continue
        if normalized_diff == norm_candidate:
            return True
        if normalized_diff.startswith(norm_candidate + "/"):
            return True
    return False


def validate_scm_diff(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    result: Result,
) -> None:
    """§11 + §21 — scm.diff_artifact must resolve and cover manifest.changed_paths."""
    scm = manifest.get("scm")
    if not isinstance(scm, dict):
        return
    diff_artifact = scm.get("diff_artifact")
    if not isinstance(diff_artifact, str):
        return
    rerun_of = manifest.get("rerun_of")
    if not diff_artifact:
        if rerun_of is None:
            # already covered by manifest_scm_diff_missing_fails
            return
        return  # evidence-only rerun, diff may be empty
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    resolution = validate_artifact_reference(
        result,
        result.product_root,
        run_folder,
        diff_artifact,
        "scm.diff_artifact",
        missing_rule_id="manifest_scm_diff_missing_fails",
        missing_message=f"scm.diff_artifact {diff_artifact!r} does not resolve",
        feature=feature_id,
        run_id=run_id,
        path=str(run_folder / diff_artifact),
    )
    diff_path = resolution.normalized_path
    common = {"feature": feature_id, "run_id": run_id, "path": str(diff_path or run_folder / diff_artifact)}
    if resolution.error_kind or diff_path is None:
        return

    diff_paths, error = parse_scm_diff_file(diff_path)
    if error == "missing":
        if rerun_of is None:
            result.add_error(
                "manifest_scm_diff_missing_fails",
                f"scm.diff_artifact {diff_artifact!r} does not resolve",
                **common,
            )
        return
    if error:
        result.add_error("manifest_scm_diff_missing_fails", f"scm.diff_artifact {diff_artifact!r} could not be read: {error}", **common)
        return

    changed_paths = manifest.get("changed_paths") or []
    if not isinstance(changed_paths, list):
        return
    manifest_paths = [str(p) for p in changed_paths if isinstance(p, str)]
    uncovered = [diff_path_value for diff_path_value in diff_paths if not _is_covered_by(diff_path_value, manifest_paths)]
    if uncovered:
        result.add_error(
            "changed_paths_missing_diff_entry_fails",
            f"scm.diff_artifact lists {len(uncovered)} path(s) not covered by manifest.changed_paths: {uncovered[:5]!r}",
            **common,
        )
    # Inverse direction — manifest entries that aren't in the diff at all may
    # indicate planning-only paths; we don't fire on those, but mismatch in scope
    # (booleans declared without any diff support) is handled by
    # scope_boolean_false_with_changed_paths_fails above.


def _absolute_cwd_justified(run_folder: Path) -> bool:
    """Check artifact-trace.md `Run Environment` block per §13."""
    trace = run_folder / "artifact-trace.md"
    content = safe_read(trace)
    if content is None:
        return False
    section = extract_section(content, "Run Environment")
    if not section:
        # May be nested under another heading; look anywhere for the entry.
        section = content
    return bool(re.search(r"-\s+Absolute cwd:\s+\S+\s+[—-]\s+\S+", section, re.IGNORECASE))


# --------------------------------------------------------------------------- #
# §21 cross-artifact consistency
# --------------------------------------------------------------------------- #


def validate_cross_artifact_identity(
    row: RegistryRow,
    manifest: dict[str, Any],
    manifest_path: Path,
    run_folder: Path,
    stage: str,
    result: Result,
) -> None:
    """§21 — feature_id / run_id / closeout path agreement across sources."""
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    common = {"feature": feature_id, "run_id": run_id, "path": str(manifest_path)}

    # feature_identity_mismatch_fails — registry, manifest, feature index folder, latest-run
    if str(manifest.get("feature_id", "")) != feature_id:
        result.add_error(
            "feature_identity_mismatch_fails",
            f"Manifest feature_id {manifest.get('feature_id')!r} disagrees with registry {feature_id!r}",
            **common,
        )
    feature_index_root = feature_index_root_for(result.product_root, row)
    if not feature_index_root.name.startswith(f"{feature_id}-"):
        result.add_error(
            "feature_identity_mismatch_fails",
            f"Feature index folder {feature_index_root.name!r} does not start with {feature_id}-",
            **common,
        )
    if run_folder.parent != evidence_runs_root(result.product_root):
        result.add_error(
            "feature_identity_mismatch_fails",
            f"Run folder {run_folder!s} is not under the canonical runs root",
            **common,
        )
    latest_path = feature_index_root / "latest-run.json"
    if latest_path.exists():
        loaded, error = load_json_file(latest_path)
        if not error and isinstance(loaded, dict):
            if str(loaded.get("feature_id", "")) != feature_id:
                result.add_error(
                    "feature_identity_mismatch_fails",
                    f"latest-run.json feature_id {loaded.get('feature_id')!r} disagrees with registry {feature_id!r}",
                    **common,
                )

    # run_identity_mismatch_fails — run folder name vs manifest.run_id vs latest-run.json.run_id
    actual_folder_name = run_folder.name
    manifest_run_id = str(manifest.get("run_id", ""))
    if manifest_run_id and manifest_run_id != actual_folder_name:
        result.add_error(
            "run_identity_mismatch_fails",
            f"Manifest run_id {manifest_run_id!r} disagrees with run folder name {actual_folder_name!r}",
            **common,
        )
    if latest_path.exists():
        loaded, error = load_json_file(latest_path)
        if not error and isinstance(loaded, dict):
            if str(loaded.get("status", "")) == "approved":
                latest_run_id = str(loaded.get("run_id", ""))
                if manifest_run_id and latest_run_id and manifest_run_id != latest_run_id and manifest.get("status") == "approved":
                    result.add_error(
                        "run_identity_mismatch_fails",
                        f"Manifest run_id {manifest_run_id!r} disagrees with latest-run.json {latest_run_id!r}",
                        **common,
                    )

    # closeout_path_mismatch_fails — at G8/closeout the registry folder must match manifest
    if stage in {"G8", "closeout"} and manifest.get("status") == "approved":
        registry_folder = row.folder.rstrip("/")
        closeout_path = manifest.get("feature_path_at_closeout") or ""
        if registry_folder and closeout_path:
            expected_suffix = f"planning-mds/features/{registry_folder}"
            if closeout_path.rstrip("/") != expected_suffix:
                result.add_error(
                    "closeout_path_mismatch_fails",
                    f"Manifest feature_path_at_closeout {closeout_path!r} disagrees with registry folder {registry_folder!r}",
                    **common,
                )


def validate_signoff_ledger_consistency(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    stage: str,
    result: Result,
) -> None:
    """§21 — signoff-ledger.md must agree with current STATUS.md rows."""
    if stage not in {"G5", "G6", "G8", "closeout"}:
        return
    ledger_path = run_folder / "signoff-ledger.md"
    ledger_content = safe_read(ledger_path)
    if ledger_content is None:
        return
    status_path = feature_path_for(result.product_root, row) / "STATUS.md"
    status_content = safe_read(status_path)
    if status_content is None:
        return
    section = _find_signoff_table(status_content)
    if not section:
        return
    rows_raw = parse_table(section)
    current: dict[tuple[str, str], dict[str, str]] = {}
    for entry in rows_raw:
        lower = {key.strip().casefold(): value for key, value in entry.items()}
        story = strip_code(lower.get("story", ""))
        role = strip_code(lower.get("role", ""))
        if not story or not role:
            continue
        current[(story, role)] = lower

    common = {
        "feature": row.feature_id,
        "run_id": manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None,
        "path": str(ledger_path),
    }
    for (story, role), entry in current.items():
        verdict_value = strip_code(entry.get("verdict", ""))
        if verdict_value.upper() not in {v.upper() for v in ROLE_PASSING_REVIEWS}:
            continue
        if story not in ledger_content or role not in ledger_content:
            result.add_error(
                "signoff_ledger_stale_fails",
                f"signoff-ledger.md does not reference current STATUS row ({story}, {role})",
                **common,
            )
            result.add_error(
                "signoff_ledger_disagrees_fails",
                f"signoff-ledger.md disagrees with STATUS.md current row ({story}, {role})",
                **common,
            )


def validate_cross_artifact_coverage_waiver(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    stage: str,
    result: Result,
) -> None:
    """§21 — coverage waiver scope/owner/date must match coverage-report.md."""
    waivers = manifest.get("waivers")
    if not isinstance(waivers, dict):
        return
    coverage = waivers.get("coverage")
    if not isinstance(coverage, dict):
        return
    coverage_path = run_folder / "coverage-report.md"
    content = safe_read(coverage_path) or ""
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    common = {"feature": feature_id, "run_id": run_id, "path": str(coverage_path)}

    owner = str(coverage.get("owner", "")).strip()
    approved_on = str(coverage.get("approved_on", "")).strip()
    reason = str(coverage.get("reason", "")).strip()
    if owner and owner not in content:
        result.add_error(
            "coverage_waiver_mismatch_fails",
            f"coverage-report.md does not name waiver owner {owner!r}",
            **common,
        )
    if approved_on and approved_on not in content:
        result.add_error(
            "coverage_waiver_mismatch_fails",
            f"coverage-report.md does not include waiver approved_on {approved_on!r}",
            **common,
        )
    if reason:
        # Look for at least a fragment of the reason in the report.
        reason_words = [word for word in re.findall(r"\w+", reason) if len(word) > 4]
        if reason_words and not any(word.casefold() in content.casefold() for word in reason_words):
            result.add_error(
                "coverage_waiver_mismatch_fails",
                "coverage-report.md does not echo the waiver reason",
                **common,
            )


def validate_cross_artifact_recommendations(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    stage: str,
    result: Result,
) -> None:
    """§21 — every PM Acceptance Line identifier that is not a recognized waiver
    key, coverage, validator-defect rule ID, or §15 keyword should map to a
    recommendation appearing somewhere in the role reports."""
    if stage not in {"G8", "closeout"}:
        return
    pm_path = run_folder / "pm-closeout.md"
    pm_content = safe_read(pm_path)
    if pm_content is None:
        return
    acceptances = parse_pm_acceptance_lines(pm_content)
    if not acceptances:
        return

    waivers = manifest.get("waivers") or {}
    waiver_keys = set(waivers.keys()) if isinstance(waivers, dict) else set()
    validator_defect = waivers.get("validator_defect") if isinstance(waivers, dict) else None
    rule_ids: set[str] = set()
    if isinstance(validator_defect, dict):
        affected = validator_defect.get("affected_rule_ids") or []
        if isinstance(affected, list):
            rule_ids = {str(item) for item in affected}

    # Gather all recommendation texts from role reports.
    rec_texts: list[str] = []
    for filename in RECOMMENDATION_BEARING_REPORTS:
        content = safe_read(run_folder / filename) or ""
        for rec in parse_recommendations(content):
            rec_texts.append(rec.text.casefold())

    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    common = {"feature": feature_id, "run_id": run_id, "path": str(pm_path)}

    for entry in acceptances:
        identifier = entry.identifier.strip()
        identifier_lower = identifier.casefold()
        if identifier_lower in {"coverage"}:
            continue
        if identifier in waiver_keys:
            continue
        if identifier in rule_ids:
            continue
        # If the identifier looks like a recommendation, it must appear in a role report.
        if any(identifier_lower in text or text in identifier_lower for text in rec_texts):
            continue
        # Story-role acceptances (status_recommendation_without_acceptance_fails) are tolerated.
        if STORY_REF_RE.fullmatch(identifier) or "-" in identifier and identifier.startswith("F"):
            continue
        result.add_error(
            "recommendation_acceptance_mismatch_fails",
            f"PM Acceptance Line identifier {identifier!r} does not match any role report recommendation, waiver key, or rule ID",
            **common,
        )


def validate_omissions_filesystem(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    result: Result,
) -> None:
    """§21 — an omitted artifact must not actually be present on disk."""
    omissions = manifest.get("omissions") or []
    if not isinstance(omissions, list):
        return
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    for omission in omissions:
        if not isinstance(omission, dict):
            continue
        artifact = omission.get("artifact")
        if not isinstance(artifact, str):
            continue
        target = run_folder / artifact
        if target.exists() and target.is_file():
            result.add_error(
                "omission_filesystem_mismatch_fails",
                f"Artifact {artifact!r} is declared as an omission but exists on disk",
                feature=feature_id,
                run_id=run_id,
                path=str(target),
            )


def validate_command_artifact_filesystem(
    row: RegistryRow,
    manifest: dict[str, Any],
    run_folder: Path,
    result: Result,
) -> None:
    """§21 — every artifact referenced from commands.log must resolve on disk.

    This is the cross-artifact form of `commands_log_artifact_missing_fails`;
    §21 names it `command_artifact_missing_fails`.
    """
    path = run_folder / "commands.log"
    if not path.exists():
        return
    text = safe_read(path) or ""
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        artifacts = record.get("artifacts") or []
        if not isinstance(artifacts, list):
            continue
        for artifact in artifacts:
            if not isinstance(artifact, str) or not artifact:
                continue
            validate_artifact_reference(
                result,
                result.product_root,
                run_folder,
                artifact,
                f"commands.log line {line_no} artifact",
                missing_rule_id="command_artifact_missing_fails",
                missing_message=f"commands.log line {line_no} artifact {artifact!r} does not resolve under product root",
                generic_missing=False,
                feature=feature_id,
                run_id=run_id,
                path=str(path),
            )


def validate_phase2b_additional_rules(
    row: RegistryRow,
    manifest: dict[str, Any],
    manifest_path: Path,
    run_folder: Path,
    stage: str,
    result: Result,
) -> None:
    """§23 closure additions completed in Phase 2b. Each block emits a distinct
    rule_id. Tests under tests/test_validate_feature_evidence_phase2b.py drive
    each scenario; the rules are grouped here for locality."""
    feature_id = row.feature_id
    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None
    common = {"feature": feature_id, "run_id": run_id, "path": str(manifest_path)}

    declared = manifest.get("required_roles") or []
    declared_set = {str(item) for item in declared if isinstance(item, str)}
    role_results = manifest.get("role_results") or {}
    role_results_required: set[str] = set()
    if isinstance(role_results, dict):
        role_results_required = {
            name for name, entry in role_results.items()
            if isinstance(entry, dict) and entry.get("required") is True
        }

    # required_roles_mismatch_fails (§21 cross-artifact form). manifest.required_roles[]
    # must equal the union of role_results required + STATUS.md effective set.
    extras_in_role_results = role_results_required - declared_set
    if extras_in_role_results:
        result.add_error(
            "required_roles_mismatch_fails",
            f"role_results lists roles required that required_roles[] omits: {sorted(extras_in_role_results)!r}",
            **common,
        )

    # deployment_changed_without_devops_fails (§7 forced role).
    if manifest.get("deployment_config_changed") is True and "DevOps" not in declared_set:
        result.add_error(
            "deployment_changed_without_devops_fails",
            "deployment_config_changed=true but DevOps is not in required_roles[]",
            **common,
        )

    # security_true_without_security_role_fails (§7 forced role).
    if manifest.get("security_sensitive_scope") is True and "Security Reviewer" not in declared_set:
        result.add_error(
            "security_true_without_security_role_fails",
            "security_sensitive_scope=true but Security Reviewer is not in required_roles[]",
            **common,
        )

    # pm_role_required_missing_report_fails (§11 PM-as-planning-role).
    pm_entry = role_results.get("Product Manager") if isinstance(role_results, dict) else None
    if isinstance(pm_entry, dict) and pm_entry.get("required") is True:
        verdict_artifact = pm_entry.get("verdict_artifact")
        if not isinstance(verdict_artifact, str) or not verdict_artifact:
            result.add_error(
                "pm_role_required_missing_report_fails",
                "Product Manager is required in role_results but its verdict_artifact is missing",
                **common,
            )
        else:
            validate_artifact_reference(
                result,
                result.product_root,
                run_folder,
                verdict_artifact,
                "Product Manager verdict_artifact",
                missing_rule_id="pm_role_required_missing_report_fails",
                missing_message="Product Manager is required in role_results but its verdict_artifact is missing",
                **common,
            )

    # latest-run.json schema rules (§12). validate_latest_run already enforces
    # wrong-manifest / mismatched-run; these add path-shape and status-enum checks.
    latest_path = feature_index_root_for(result.product_root, row) / "latest-run.json"
    if latest_path.exists():
        loaded, _ = load_json_file(latest_path)
        if isinstance(loaded, dict):
            for field in ("run_path", "manifest_path"):
                value = loaded.get(field)
                if isinstance(value, str) and value:
                    absolute, _ = _is_repo_relative(value)
                    if absolute:
                        result.add_error(
                            "latest_run_absolute_path_fails",
                            f"latest-run.json {field}={value!r} is absolute; must be repo-relative",
                            feature=feature_id, run_id=run_id, path=str(latest_path),
                        )
            status_value = loaded.get("status")
            if status_value is not None and status_value != "approved":
                result.add_error(
                    "latest_run_bad_status_fails",
                    f"latest-run.json status={status_value!r}; only 'approved' satisfies completed terminal validation",
                    feature=feature_id, run_id=run_id, path=str(latest_path),
                )

    # manifest_rerun_of_unknown_run_fails (§11 rerun_of contract).
    rerun_of = manifest.get("rerun_of")
    if isinstance(rerun_of, str) and rerun_of:
        prior_folder = evidence_runs_root(result.product_root) / rerun_of
        prior_manifest = prior_folder / "evidence-manifest.json"
        if not prior_manifest.exists():
            result.add_error(
                "manifest_rerun_of_unknown_run_fails",
                f"rerun_of={rerun_of!r} references a run folder with no manifest",
                **common,
            )
        else:
            prior_doc, _err = load_json_file(prior_manifest)
            if not isinstance(prior_doc, dict) or prior_doc.get("status") not in {"approved", "superseded"}:
                result.add_error(
                    "manifest_rerun_of_unknown_run_fails",
                    f"rerun_of={rerun_of!r} run is present but not in an approved/superseded state",
                    **common,
                )

    # Frontend global lane rules (§20).
    global_refs = manifest.get("global_evidence_refs") if isinstance(manifest.get("global_evidence_refs"), dict) else {}
    fq_ref = global_refs.get("frontend_quality") if isinstance(global_refs, dict) else None
    fq_candidates = [fq_ref] if isinstance(fq_ref, str) else (
        [v for v in fq_ref if isinstance(v, str)] if isinstance(fq_ref, list) else []
    )
    for candidate in fq_candidates:
        resolution = validate_artifact_reference(
            result,
            result.product_root,
            run_folder,
            candidate,
            "frontend_quality reference",
            missing_rule_id="frontend_global_ref_missing_fails",
            missing_message=f"frontend_quality reference {candidate!r} does not resolve",
            **common,
        )
        target = resolution.normalized_path
        if not resolution.exists or target is None:
            continue
        loaded, _ = load_json_file(target)
        if not isinstance(loaded, dict):
            result.add_error(
                "frontend_quality_bad_latest_run_fails",
                f"frontend-quality latest-run at {candidate!r} is unparseable or not an object",
                **common,
            )
            continue
        if loaded.get("status") != "approved":
            result.add_error(
                "frontend_quality_bad_latest_run_fails",
                f"frontend-quality latest-run at {candidate!r} status must be 'approved'",
                **common,
            )
    fux_ref = global_refs.get("frontend_ux") if isinstance(global_refs, dict) else None
    fux_candidates = [fux_ref] if isinstance(fux_ref, str) else (
        [v for v in fux_ref if isinstance(v, str)] if isinstance(fux_ref, list) else []
    )
    for candidate in fux_candidates:
        validate_artifact_reference(
            result,
            result.product_root,
            run_folder,
            candidate,
            "frontend_ux reference",
            missing_rule_id="frontend_ux_ref_missing_fails",
            missing_message=f"frontend_ux reference {candidate!r} does not resolve",
            **common,
        )

    # frontend_true_without_feature_test_notes_fails / frontend_global_substituted_for_feature_report_fails.
    if manifest.get("frontend_in_scope") is True and stage in {"G2", "G3", "G4", "G5", "G6", "G7", "G8", "closeout"}:
        te_path = run_folder / "test-execution-report.md"
        te_content = safe_read(te_path) or ""
        cleaned = te_content.strip()
        if cleaned and "frontend" not in cleaned.casefold():
            result.add_error(
                "frontend_true_without_feature_test_notes_fails",
                "frontend_in_scope=true but test-execution-report.md has no feature-level frontend notes",
                **common,
            )
        if cleaned:
            body_lines = [line for line in cleaned.splitlines() if line.strip() and not line.lstrip().startswith("#")]
            non_ref_lines = [line for line in body_lines if "frontend-quality" not in line and "frontend-ux" not in line]
            if body_lines and not non_ref_lines:
                result.add_error(
                    "frontend_global_substituted_for_feature_report_fails",
                    "test-execution-report.md only points at the global frontend lane; feature-level notes are required",
                    **common,
                )

    # stage_g8_requires_tracker_results_fails — at G8/closeout the
    # lifecycle-gates.log must reference the tracker-sync invocation.
    if stage in {"G8", "closeout"}:
        log_path = run_folder / "lifecycle-gates.log"
        log_content = safe_read(log_path) or ""
        if not re.search(r"validate-trackers|tracker.?sync", log_content, re.IGNORECASE):
            result.add_error(
                "stage_g8_requires_tracker_results_fails",
                "G8/closeout requires tracker-sync results to appear in lifecycle-gates.log before final validation",
                **common,
            )

    # Generated KG layers must be rebuilt, not only checked from a previously
    # committed snapshot. G7 owns the code-path-derived layers; G8/closeout adds
    # the path-sensitive coverage layer after the feature archive move.
    if kg_generated_regeneration_required(manifest, stage):
        flags = successful_kg_generated_command_flags(run_folder / "commands.log")
        required = [
            "symbol regeneration",
            "symbol validation",
            "decision regeneration",
            "decision validation",
        ]
        if stage in {"G8", "closeout"}:
            required.append("coverage report regeneration")
        missing = [flag for flag in required if not flags.get(flag, False)]
        if missing:
            result.add_error(
                "kg_generated_regeneration_missing_fails",
                "KG reconciliation must record successful generated-layer rebuild evidence in commands.log: "
                "`validate.py --regenerate-symbols --check-symbols "
                "--regenerate-decisions --check-decisions` at G7, plus "
                "`validate.py --write-coverage-report` after the G8 archive move; "
                f"missing {', '.join(missing)}",
                **common,
            )

    # Artifact-reference cross-checks (§10 / §21).
    coverage_content = safe_read(run_folder / "coverage-report.md") or ""
    for ref in artifact_references(coverage_content, "artifacts/coverage/"):
        validate_artifact_reference(
            result,
            result.product_root,
            run_folder,
            ref,
            "coverage-report.md artifact reference",
            missing_rule_id="coverage_claim_without_artifact_fails",
            missing_message=f"coverage-report.md references {ref!r} but the artifact is missing",
            **common,
        )
    te_content = safe_read(run_folder / "test-execution-report.md") or ""
    for ref in artifact_references(te_content, "artifacts/test-results/"):
        validate_artifact_reference(
            result,
            result.product_root,
            run_folder,
            ref,
            "test-execution-report.md artifact reference",
            missing_rule_id="test_results_reference_missing_fails",
            missing_message=f"test-execution-report.md references {ref!r} but the artifact is missing",
            **common,
        )
    sec_content = safe_read(run_folder / "security-review-report.md") or ""
    for ref in artifact_references(sec_content, "artifacts/security/"):
        validate_artifact_reference(
            result,
            result.product_root,
            run_folder,
            ref,
            "security-review-report.md artifact reference",
            missing_rule_id="security_scan_reference_missing_fails",
            missing_message=f"security-review-report.md references {ref!r} but the artifact is missing",
            **common,
        )
    for source in ("test-execution-report.md", "code-review-report.md"):
        body = safe_read(run_folder / source) or ""
        for ref in artifact_references(body, "artifacts/screenshots/"):
            validate_artifact_reference(
                result,
                result.product_root,
                run_folder,
                ref,
                f"{source} screenshot reference",
                missing_rule_id="screenshot_reference_missing_fails",
                missing_message=f"{source} references {ref!r} but the screenshot is missing",
                **common,
            )

    # changed_paths_mismatch_fails (§21) — role reports may mention paths that
    # the manifest's changed_paths does not cover. Limited to the obvious
    # surface (code-review-report.md) to keep false positives down.
    if stage in {"G5", "G6", "G7", "G8", "closeout"} and manifest.get("rerun_of") is None:
        changed_paths_list = manifest.get("changed_paths") or []
        manifest_paths = [str(p) for p in changed_paths_list if isinstance(p, str)]
        if manifest_paths:
            cr_content = safe_read(run_folder / "code-review-report.md") or ""
            mentioned = set(re.findall(r"(?:engine|experience|neuron|planning-mds|api|scripts)/[\w./\-]+", cr_content))
            uncovered = sorted(m for m in mentioned if not _is_covered_by(m, manifest_paths))
            if uncovered:
                result.add_error(
                    "changed_paths_mismatch_fails",
                    f"code-review-report.md mentions paths not covered by manifest.changed_paths: {uncovered[:5]!r}",
                    **common,
                )

    # deferred_blocker_passes_fails (§18) — a critical recommendation deferred
    # without explicit PM mitigation language with a passing closeout.
    if stage in {"G8", "closeout"}:
        pm_content = safe_read(run_folder / "pm-closeout.md") or ""
        for filename in RECOMMENDATION_BEARING_REPORTS:
            content = safe_read(run_folder / filename) or ""
            for rec in parse_recommendations(content):
                if rec.severity == "critical" and "defer" in (rec.follow_up or "").casefold():
                    rec_text_lower = rec.text.casefold()
                    pm_lower = pm_content.casefold()
                    if "mitigation:" not in pm_lower or rec_text_lower not in pm_lower:
                        result.add_error(
                            "deferred_blocker_passes_fails",
                            f"{filename} defers a critical recommendation without PM mitigation acceptance",
                            **common,
                        )
                        break


def validate_cross_artifact_consistency(
    row: RegistryRow,
    manifest: dict[str, Any],
    manifest_path: Path,
    run_folder: Path,
    stage: str,
    result: Result,
) -> None:
    """Run all §21 cross-artifact rules."""
    validate_cross_artifact_identity(row, manifest, manifest_path, run_folder, stage, result)
    validate_scm_diff(row, manifest, run_folder, result)
    validate_scope_booleans_against_paths(row, manifest, result, manifest_path)
    validate_signoff_ledger_consistency(row, manifest, run_folder, stage, result)
    validate_cross_artifact_coverage_waiver(row, manifest, run_folder, stage, result)
    validate_cross_artifact_recommendations(row, manifest, run_folder, stage, result)
    validate_omissions_filesystem(row, manifest, run_folder, result)
    validate_command_artifact_filesystem(row, manifest, run_folder, result)
    validate_phase2b_additional_rules(row, manifest, manifest_path, run_folder, stage, result)


# --------------------------------------------------------------------------- #
# §22 validator-defect waiver downgrade algorithm
# --------------------------------------------------------------------------- #


def apply_validator_defect_downgrades(result: Result, manifest: dict[str, Any] | None) -> None:
    """Per §22 — demote errors whose rule_id is covered by a well-formed
    `waivers.validator_defect` entry to a single `validator_defect_waived_warns`
    warning. Runs after all rules have emitted.
    """
    if not isinstance(manifest, dict):
        return
    waivers = manifest.get("waivers")
    if not isinstance(waivers, dict):
        return
    defect = waivers.get("validator_defect")
    if not isinstance(defect, dict):
        return

    required_fields = ["defect_description", "affected_rule_ids", "approved_by", "approved_on", "follow_up_owner", "follow_up_target_date"]
    for field_name in required_fields:
        if field_name not in defect:
            return  # malformed waiver — no downgrade
    affected = defect.get("affected_rule_ids") or []
    if not isinstance(affected, list) or not affected:
        return
    affected_set = {str(item) for item in affected}
    target_date = parse_iso_date(str(defect.get("follow_up_target_date", "")))
    if target_date is None:
        return
    recorded_on = parse_iso_date(str(manifest.get("recorded_on", "")))
    if recorded_on and target_date < recorded_on:
        return

    # The pm-closeout mirror check is performed by validate_validator_defect_waiver
    # which would have already emitted a violation; we still downgrade affected
    # rule errors below to avoid double-blocking, since the mirror failure rule
    # is itself part of the surface.

    kept_errors: list[Finding] = []
    downgraded: list[Finding] = []
    for finding in result.errors:
        if finding.rule_id in affected_set:
            downgraded.append(finding)
        else:
            kept_errors.append(finding)
    if not downgraded:
        return
    result.errors = kept_errors
    follow_up_owner = str(defect.get("follow_up_owner", "?"))
    target_text = target_date.isoformat()
    for finding in downgraded:
        result.add_warning(
            "validator_defect_waived_warns",
            f"Rule {finding.rule_id} waived by validator_defect (owner {follow_up_owner!r}, target {target_text}): {finding.message}",
            feature=finding.feature,
            run_id=finding.run_id,
            path=finding.path,
        )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def validate_manifest(
    row: RegistryRow,
    run_id: str | None,
    manifest_path: Path | None,
    result: Result,
    stage: str,
    secret_scanner: SecretScanner,
) -> dict[str, Any] | None:
    if manifest_path is None:
        return None
    if not manifest_path.exists():
        result.add_error(
            "missing_manifest_fails",
            "evidence-manifest.json is missing",
            feature=row.feature_id,
            run_id=run_id or None,
            path=str(manifest_path),
        )
        return None
    loaded, error = load_json_file(manifest_path)
    if error or not isinstance(loaded, dict):
        result.add_error(
            "manifest_unparseable_fails",
            "evidence-manifest.json is not valid JSON",
            feature=row.feature_id,
            run_id=run_id or None,
            path=str(manifest_path),
        )
        return None
    common = {"feature": row.feature_id, "run_id": run_id or None, "path": str(manifest_path)}

    schema_version = loaded.get("schema_version")
    if schema_version not in SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
        result.add_error(
            "manifest_bad_schema_version_fails",
            f"Manifest schema_version {schema_version!r} is not supported (expected one of {sorted(SUPPORTED_MANIFEST_SCHEMA_VERSIONS)})",
            **common,
        )
        return None
    manifest_feature_id = str(loaded.get("feature_id", ""))
    if manifest_feature_id != row.feature_id:
        result.add_error("manifest_feature_id_mismatch_fails", "Manifest feature_id does not match registry feature", **common)
    manifest_run_id = str(loaded.get("run_id", ""))
    if not RUN_ID_RE.fullmatch(manifest_run_id):
        result.add_error("manifest_bad_run_id_fails", "Manifest run_id is malformed", feature=row.feature_id, run_id=manifest_run_id or None, path=str(manifest_path))
    elif run_id and manifest_run_id != run_id:
        result.add_error("manifest_bad_run_id_fails", "Manifest run_id does not match selected run folder", feature=row.feature_id, run_id=manifest_run_id, path=str(manifest_path))
    status_value = str(loaded.get("status", ""))
    if status_value and status_value not in MANIFEST_STATUSES:
        result.add_error("manifest_bad_status_fails", "Manifest status is not a supported value", **common)
    if stage == "closeout" and status_value and status_value != "approved":
        result.add_error("manifest_bad_status_fails", "Closeout validation requires manifest status approved", **common)

    # Date sanity
    if parse_iso_date(str(loaded.get("recorded_on", ""))) is None:
        result.add_error("manifest_bad_recorded_on_fails", "Manifest recorded_on is not a parseable ISO date", **common)
    if parse_iso_date(str(loaded.get("contract_effective_date", ""))) is None:
        result.add_error("manifest_bad_effective_date_fails", "Manifest contract_effective_date is not a parseable ISO date", **common)

    # Start path shape
    start_path = str(loaded.get("feature_path_at_run_start", ""))
    if not start_path or not start_path.startswith("planning-mds/features/"):
        result.add_error("manifest_bad_start_path_fails", "feature_path_at_run_start must start with planning-mds/features/", **common)

    # Slug
    slug = str(loaded.get("feature_slug", ""))
    if slug:
        if row.evidence_slug and slug not in row.evidence_slug and slug not in row.folder:
            result.add_error("manifest_slug_mismatch_fails", f"Manifest feature_slug {slug!r} does not match registry folder", **common)

    # Two-approved supersession check
    if status_value == "approved":
        other_approved: list[Path] = []
        for sibling_manifest in feature_manifests(result.product_root, row.feature_id):
            if sibling_manifest == manifest_path:
                continue
            sibling_doc, sibling_error = load_json_file(sibling_manifest)
            if sibling_error or not isinstance(sibling_doc, dict):
                continue
            if sibling_doc.get("status") == "approved":
                other_approved.append(sibling_manifest)
        if other_approved:
            result.add_error(
                "two_approved_runs_without_supersession_fails",
                f"Feature has multiple approved manifests: {[str(p) for p in other_approved]}",
                **common,
            )

    validate_manifest_deep(row, run_id, loaded, manifest_path, result, stage)
    return loaded


def validate_governed_row(
    row: RegistryRow,
    result: Result,
    stage: str,
    run_id: str | None,
    secret_scanner: SecretScanner,
) -> None:
    selected_run_id, manifest_path, _ = resolve_run(row, stage, run_id, result)
    before_errors = len(result.errors)
    manifest = validate_manifest(row, selected_run_id, manifest_path, result, stage, secret_scanner)
    if manifest_path is not None and manifest is not None:
        run_folder = manifest_path.parent
        if run_folder.exists():
            status_required = parse_status_required_roles(row, result)
            validate_required_artifacts(row, manifest, run_folder, stage, result)
            validate_gate_decisions(run_folder, manifest, stage, row, result)
            validate_lifecycle_gates(run_folder, row, result)
            validate_commands_log(run_folder, manifest, secret_scanner, row, result)
            validate_role_and_gate_results(row, manifest, run_folder, stage, result, status_required)
            validate_status_md(row, manifest, run_folder, stage, result)
            validate_recommendations_in_role_reports(row, manifest, run_folder, stage, result)
            validate_coverage_waiver_acceptance(row, manifest, run_folder, stage, result)
            validate_validator_defect_waiver(row, manifest, run_folder, stage, result)
            validate_cross_artifact_consistency(row, manifest, manifest_path, run_folder, stage, result)
            apply_validator_defect_downgrades(result, manifest)
    if len(result.errors) == before_errors:
        result.features_validated += 1


def validate(args: argparse.Namespace, product_root: Path, effective_date: date, secret_scanner: SecretScanner) -> tuple[Result, int]:
    stage = args.stage or "closeout"
    result = Result(stage=stage, product_root=product_root, effective_date=effective_date)
    rows = load_registry(product_root, result)
    if any(error.rule_id == "registry_missing_fails" for error in result.errors):
        return result, 2
    if args.feature and args.feature not in rows:
        result.errors.clear()
        result.add_error("feature_not_in_registry_fails", f"{args.feature} is not present in REGISTRY.md")
        return result, 2
    if any(error.rule_id == "registry_required_section_missing_fails" for error in result.errors):
        return result, 1

    if args.evidence_effective_date and effective_date > DEFAULT_EFFECTIVE_DATE:
        result.add_warning(
            "effective_date_overridden_warns",
            f"--evidence-effective-date {effective_date.isoformat()} overrides default {DEFAULT_EFFECTIVE_DATE.isoformat()}",
        )

    if args.feature:
        row = rows[args.feature]
        if row.section == "Retired Features":
            classify_retired(row, result)
            result.add_info("retired_feature_explicit_target_info", "Feature is retired; completion evidence validation skipped", feature=row.feature_id)
            return result, 0
        if row.section == "Archived Features":
            row_archived_date = archived_date(row)
            reentry = evidence_reentry_date(row)
            if row_archived_date is None:
                result.add_error("archived_missing_date_fails", "Archived feature is missing a parseable Archived Date", feature=row.feature_id)
                return result, 1
            if row_archived_date < effective_date and (reentry is None or reentry < effective_date):
                result.features_skipped_pre_contract_archived += 1
                result.add_info("pre_contract_archived_explicit_target_info", "Pre-contract archived feature; completion evidence validation skipped", feature=row.feature_id)
                return result, 0
            if row_archived_date < effective_date and reentry is not None and reentry >= effective_date:
                emit_reopened_reentry_rule_if_missing(row, product_root, result)
        if row.section == "Active Features":
            if not is_terminal_active(row):
                return result, 0
            _, shape = extract_closeout_review_date_with_shape(feature_path_for(product_root, row))
            if shape == "malformed":
                emit_malformed_closeout_date_rule_if_missing(row, product_root, result)
        validate_governed_row(row, result, stage, args.run_id, secret_scanner)
        return result, 1 if result.errors else 0

    for row in governed_rows(rows, product_root, result, effective_date):
        validate_governed_row(row, result, stage, args.run_id, secret_scanner)
    return result, 1 if result.errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate feature evidence packages.")
    parser.add_argument("--product-root", default=None)
    parser.add_argument("--feature", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--stage", default="closeout", choices=sorted(STAGES))
    parser.add_argument("--evidence-effective-date", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--json-out", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    product_root = resolve_product_root(args.product_root)
    effective_date = parse_effective_date(args.evidence_effective_date)

    if args.json and args.json_out:
        return invocation_failure(args, product_root, effective_date, "cli_json_flags_conflict_fails", "--json and --json-out are mutually exclusive")
    if not product_root.exists() or not product_root.is_dir():
        return invocation_failure(args, product_root, effective_date, "cli_product_root_invalid_fails", "--product-root does not exist or is not a directory")
    if args.run_id and not RUN_ID_RE.fullmatch(args.run_id):
        return invocation_failure(args, product_root, effective_date, "cli_run_id_malformed_fails", "--run-id is malformed")
    if effective_date == date.min or effective_date < DEFAULT_EFFECTIVE_DATE:
        return invocation_failure(args, product_root, effective_date, "effective_date_override_earlier_than_default_fails", "--evidence-effective-date is earlier than the framework default")
    secret_rule, secret_patterns = validate_secret_patterns(product_root)
    if secret_rule:
        return invocation_failure(args, product_root, effective_date, secret_rule, "secret pattern configuration failed to load or validate")
    if not validate_path_class_extensions(product_root):
        return invocation_failure(args, product_root, effective_date, "path_class_extension_conflict_fails", "Path Class Extensions conflict with framework defaults")

    secret_scanner = build_secret_scanner(secret_patterns)
    result, exit_code = validate(args, product_root, effective_date, secret_scanner)
    return output_result(result, args, exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
