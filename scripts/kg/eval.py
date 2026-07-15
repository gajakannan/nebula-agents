#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

import hint
import lookup
from kg_common import REF_FIELDS, REPO_ROOT, build_bundle, edge_ref_ids, feature_or_story_by_id
from kg_usage import cache_metrics

STATUS_PATH_RE = "planning-mds/features/"
MAPPINGS_PATH = "planning-mds/knowledge-graph/feature-mappings.yaml"
# Local dev telemetry (gitignored) + committed operations telemetry (usage/cost stream).
TELEMETRY_GLOBS = (".kg-state/**/*.jsonl", "planning-mds/operations/telemetry/**/*.jsonl")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
    )


def git_lines(*args: str) -> list[str]:
    return [line for line in git(*args).splitlines() if line.strip()]


def load_yaml_at_ref(ref: str, path: str) -> dict[str, Any]:
    content = git("show", f"{ref}:{path}")
    return yaml.safe_load(content) or {}


def load_bundle_at_ref(ref: str) -> dict[str, Any]:
    return build_bundle(
        load_yaml_at_ref(ref, "planning-mds/knowledge-graph/solution-ontology.yaml"),
        load_yaml_at_ref(ref, "planning-mds/knowledge-graph/canonical-nodes.yaml"),
        load_yaml_at_ref(ref, "planning-mds/knowledge-graph/feature-mappings.yaml"),
        load_yaml_at_ref(ref, "planning-mds/knowledge-graph/code-index.yaml"),
    )


def commit_list(since: str | None, feature_id: str | None, limit: int | None) -> list[str]:
    if feature_id:
        current_bundle = build_bundle(
            load_yaml_at_ref("HEAD", "planning-mds/knowledge-graph/solution-ontology.yaml"),
            load_yaml_at_ref("HEAD", "planning-mds/knowledge-graph/canonical-nodes.yaml"),
            load_yaml_at_ref("HEAD", "planning-mds/knowledge-graph/feature-mappings.yaml"),
            load_yaml_at_ref("HEAD", "planning-mds/knowledge-graph/code-index.yaml"),
        )
        feature = feature_or_story_by_id(f"feature:{feature_id}", current_bundle["mappings"])
        paths = [MAPPINGS_PATH]
        if feature and feature.get("path"):
            paths.append(feature["path"])
        args = ["log", "--format=%H", "--reverse"]
        if since:
            args.append(f"{since}..HEAD")
        args.append("--")
        args.extend(paths)
        commits = git_lines(*args)
    elif since:
        commits = git_lines("rev-list", "--reverse", f"{since}..HEAD")
    else:
        commits = git_lines("rev-list", "--reverse", "HEAD")

    if limit is not None and limit > 0:
        return commits[-limit:]
    return commits


def changed_files(commit: str) -> list[str]:
    return git_lines("show", "--pretty=", "--name-only", commit)


def closeout_feature_ids(commit: str, files: list[str]) -> list[str]:
    if MAPPINGS_PATH not in files:
        return []

    feature_ids: set[str] = set()
    for path in files:
        if not path.endswith("/STATUS.md"):
            continue
        if not path.startswith(STATUS_PATH_RE):
            continue
        leaf = Path(path).parts[-2]
        if leaf.startswith("F") and "-" in leaf:
            feature_ids.add(leaf.split("-", 1)[0])
    return sorted(feature_ids)


def canonical_node_ids(feature_id: str, bundle: dict[str, Any]) -> set[str]:
    feature = feature_or_story_by_id(f"feature:{feature_id}", bundle["mappings"])
    if feature is None:
        return set()

    refs: set[str] = set()
    for field in REF_FIELDS:
        refs.update(edge_ref_ids(feature.get(field, [])))
    return {node_id for node_id in refs if node_id in bundle["canonical_nodes"]}


def hint_node_ids_for_paths(paths: list[str], bundle: dict[str, Any]) -> set[str]:
    matched: set[str] = set()
    for path in paths:
        try:
            matches = hint.match_path(path, bundle)
        except Exception:
            continue
        matched.update(match["id"] for match in matches)
    return matched


def precision_recall(predicted: set[str], expected: set[str]) -> tuple[float, float]:
    if not predicted and not expected:
        return 1.0, 1.0
    if not predicted:
        return 0.0, 0.0
    if not expected:
        return 0.0, 1.0
    intersection = predicted & expected
    return len(intersection) / len(predicted), len(intersection) / len(expected)


def tier3_declared_paths(feature_id: str, bundle: dict[str, Any]) -> set[str]:
    payload = lookup.lookup_by_target(
        feature_id,
        bundle,
        tier=3,
        fields="full",
        allow_missing=False,
    )
    declared: set[str] = set()
    for field in REF_FIELDS:
        for entry in payload.get(field, []):
            if not isinstance(entry, dict):
                continue
            if entry.get("path"):
                declared.add(entry["path"])
            declared.update(entry.get("source_docs", []))
    return declared


def load_telemetry_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for glob in TELEMETRY_GLOBS:
        for path in REPO_ROOT.glob(glob):
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def retrieval_by_source(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group non-usage telemetry by `source` so MCP retrievals (`source="mcp"`) can be
    compared against CLI ones (CLI events have no/None source -> labelled "cli")."""
    groups: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("tool") == "turn":  # harness usage turns are covered by cache_metrics
            continue
        source = event.get("source") or "cli"
        group = groups.setdefault(source, {"events": 0, "tokens_estimated": 0, "by_tool": {}})
        group["events"] += 1
        tokens = (event.get("payload") or {}).get("tokens_estimated")
        if isinstance(tokens, (int, float)):
            group["tokens_estimated"] += tokens
        tool = event.get("tool")
        group["by_tool"][tool] = group["by_tool"].get(tool, 0) + 1
    return groups


def group_runs(events: list[dict[str, Any]], feature_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        run_id = event.get("run_id")
        if not run_id:
            continue
        if feature_ids and event.get("feature_id") not in feature_ids:
            continue
        runs[run_id].append(event)
    return runs


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * pct))))
    return ordered[index]


def telemetry_metrics(events: list[dict[str, Any]], feature_ids: set[str]) -> dict[str, Any]:
    runs = group_runs(events, feature_ids)
    if not runs:
        return {
            "empty_lookup_rate": None,
            "ambiguous_match_rate": None,
            "escalation_rate": None,
            "tier_escalation_rate": None,
            "token_cost_per_successful_run": {"mean": None, "p95": None},
            "tier_vs_outcome": [],
        }

    lookup_events = [
        event
        for event in events
        if event.get("tool") == "lookup" and event.get("run_id") in runs
    ]
    empty_lookup_rate = (
        sum(1 for event in lookup_events if event.get("payload", {}).get("empty_scope")) / len(lookup_events)
        if lookup_events
        else None
    )
    ambiguous_match_rate = (
        sum(1 for event in lookup_events if event.get("payload", {}).get("ambiguous_count", 0) > 0) / len(lookup_events)
        if lookup_events
        else None
    )

    escalation_rate = sum(
        1
        for run_events in runs.values()
        if any(event.get("tool") == "workstate-escalate" for event in run_events)
    ) / len(runs)

    tier_escalated_runs = 0
    bucket_totals: dict[tuple[str | None, Any], list[bool]] = defaultdict(list)
    token_costs: list[float] = []

    for run_events in runs.values():
        run_lookup_events = [event for event in run_events if event.get("tool") == "lookup"]
        if not run_lookup_events:
            continue
        start_tier = run_lookup_events[0].get("payload", {}).get("tier_requested")
        final_tier = max(
            event.get("payload", {}).get("tier_returned") or 0 for event in run_lookup_events
        )
        if isinstance(start_tier, int) and isinstance(final_tier, int) and final_tier > start_tier:
            tier_escalated_runs += 1

        mode = run_lookup_events[0].get("mode")
        no_escalation = not any(event.get("tool") == "workstate-escalate" for event in run_events)
        bucket_totals[(mode, start_tier)].append(no_escalation)
        token_costs.append(
            sum(event.get("payload", {}).get("tokens_estimated", 0) for event in run_events)
        )

    tier_vs_outcome = [
        {
            "mode": mode,
            "start_tier": start_tier,
            "done_without_escalation_rate": sum(outcomes) / len(outcomes),
            "runs": len(outcomes),
        }
        for (mode, start_tier), outcomes in sorted(bucket_totals.items(), key=lambda item: (str(item[0][0]), str(item[0][1])))
    ]

    return {
        "empty_lookup_rate": empty_lookup_rate,
        "ambiguous_match_rate": ambiguous_match_rate,
        "escalation_rate": escalation_rate,
        "tier_escalation_rate": tier_escalated_runs / len(runs),
        "token_cost_per_successful_run": {
            "mean": mean(token_costs) if token_costs else None,
            "p95": percentile(token_costs, 0.95),
        },
        "tier_vs_outcome": tier_vs_outcome,
    }


def render_human(report: dict[str, Any]) -> str:
    lines = [
        "KG Retrieval Eval",
        "-" * 60,
        f"Commits evaluated: {len(report['commits'])}",
        f"Node precision:    {report['node_precision']:.3f}",
        f"Node recall:       {report['node_recall']:.3f}",
    ]
    telemetry = report["telemetry"]
    lines.extend(
        [
            f"Empty lookup rate: {telemetry['empty_lookup_rate'] if telemetry['empty_lookup_rate'] is not None else 'n/a'}",
            f"Ambiguous rate:    {telemetry['ambiguous_match_rate'] if telemetry['ambiguous_match_rate'] is not None else 'n/a'}",
            f"Escalation rate:   {telemetry['escalation_rate'] if telemetry['escalation_rate'] is not None else 'n/a'}",
            f"Tier escalation:   {telemetry['tier_escalation_rate'] if telemetry['tier_escalation_rate'] is not None else 'n/a'}",
        ]
    )
    token_costs = telemetry["token_cost_per_successful_run"]
    lines.append(
        "Token cost/run:    "
        f"mean={token_costs['mean'] if token_costs['mean'] is not None else 'n/a'}, "
        f"p95={token_costs['p95'] if token_costs['p95'] is not None else 'n/a'}"
    )
    cache = report.get("cache") or {}
    if cache.get("turns"):  # only render when harness usage was ingested (else byte-identical to before)
        cpt = cache.get("cost_per_turn", {})
        lines.append(
            f"Cache hit ratio:   {cache['cache_hit_ratio'] if cache['cache_hit_ratio'] is not None else 'n/a'} "
            f"(turns={cache['turns']})"
        )
        lines.append(
            "Cost/turn:         "
            f"mean={cpt.get('mean', 'n/a')}, p95={cpt.get('p95', 'n/a')} "
            f"({cache.get('cost_unit', 'input-token-equivalents')})"
        )
        for s in cache.get("cache_write_spikes", []):
            lines.append(
                f"  ! cache-write spike {s['x_median']}x median "
                f"(write_share={s['write_share']}, sidechain={s['is_sidechain']})"
            )
    by_source = report.get("retrieval_by_source") or {}
    if by_source:
        lines.append("")
        lines.append("Retrieval by source:")
        for source in sorted(by_source):
            g = by_source[source]
            tools = ", ".join(f"{t}={n}" for t, n in sorted(g["by_tool"].items()))
            lines.append(f"- {source}: {g['events']} event(s), ~{g['tokens_estimated']} tok est  [{tools}]")
    if telemetry["tier_vs_outcome"]:
        lines.append("")
        lines.append("Tier vs outcome:")
        for entry in telemetry["tier_vs_outcome"]:
            lines.append(
                f"- mode={entry['mode']}, start_tier={entry['start_tier']}: "
                f"{entry['done_without_escalation_rate']:.3f} over {entry['runs']} run(s)"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline evaluation for KG retrieval decisions.")
    parser.add_argument("--since", default=None, help="Git ref range start, e.g. HEAD~20.")
    parser.add_argument("--feature", default=None, help="Feature ID to evaluate, e.g. F0016.")
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Keep at most the last N commits from the walk (default 200, 0 disables the cap).",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON instead of the human-readable summary.")
    args = parser.parse_args()

    commits = commit_list(args.since, args.feature, args.limit)
    telemetry_events = load_telemetry_events()

    commit_reports: list[dict[str, Any]] = []
    precisions: list[float] = []
    recalls: list[float] = []
    feature_ids_seen: set[str] = set()

    for commit in commits:
        files = changed_files(commit)
        features = closeout_feature_ids(commit, files)
        if args.feature:
            features = [feature_id for feature_id in features if feature_id == args.feature]
        if not features:
            continue

        bundle = load_bundle_at_ref(commit)
        code_paths = [path for path in files if Path(path).suffix or path.startswith(("engine/", "experience/", "neuron/", "scripts/"))]
        predicted = hint_node_ids_for_paths(code_paths, bundle)
        tier3_paths: set[str] = set()

        for feature_id in features:
            expected = canonical_node_ids(feature_id, bundle)
            precision, recall = precision_recall(predicted, expected)
            precisions.append(precision)
            recalls.append(recall)
            feature_ids_seen.add(feature_id)

            tier3_paths |= tier3_declared_paths(feature_id, bundle)
            commit_reports.append(
                {
                    "commit": commit,
                    "feature_id": feature_id,
                    "touched_code_paths": code_paths,
                    "expected_node_ids": sorted(expected),
                    "predicted_node_ids": sorted(predicted),
                    "node_precision": precision,
                    "node_recall": recall,
                    "tier3_file_subset_advisory": all(path in tier3_paths for path in code_paths),
                }
            )

    report = {
        "commits": commit_reports,
        "node_precision": mean(precisions) if precisions else 0.0,
        "node_recall": mean(recalls) if recalls else 0.0,
        "telemetry": telemetry_metrics(telemetry_events, feature_ids_seen),
        "cache": cache_metrics(telemetry_events),
        "retrieval_by_source": retrieval_by_source(telemetry_events),
    }

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(render_human(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
