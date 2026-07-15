#!/usr/bin/env python3
"""Three-way semantic merge for tracker markdown tables (F0006-S0002).

REGISTRY.md and ROADMAP.md feature tables are merged as record sets keyed by
feature ID (a row is a record; cells are scalar fields), reusing the S0001
record engine and conflict taxonomy. Row ordering is never a conflict — it
is recomputed from each table's configured rule. Surrounding prose merges as
ordinary text (with an append-tolerant rule); prose that truly diverges
conflicts and routes to the PM, as do all tracker conflicts.

Invoked through `merge3.py <tracker>.md --base ... --ours ... --theirs ...`
(one CLI, file-type dispatch). STORY-INDEX.md is generated — never merged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dataclass_field
from typing import Any

from merge3 import Conflict, MergeEngine, _MISSING

FEATURE_ID_RE = re.compile(r"F\d{4}")
HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$")

# Generated tracker outputs — never merge inputs.
GENERATED_TRACKER_BASENAMES = frozenset({"STORY-INDEX.md"})

# Per-table configuration. `order` is one of:
#   ("id_asc",)               — sort by feature ID ascending (active tables)
#   ("date_desc", <column>)   — newest-first by <column>, feature-ID-desc
#                               tiebreak (the published PR #47 resolution rule)
#   ("manual",)               — authored order is semantic: adopt a changed
#                               side's order; when both sides only *added*
#                               rows, weave the additions in (ours' insertions
#                               first at equal anchors); real double reorders
#                               conflict.
# `exclusive_groups` lists section sets in which one feature may appear only
# once after the merge (section membership is a field: a double move
# conflicts, PM-routed).
TRACKER_CONFIGS: dict[str, dict[str, Any]] = {
    "REGISTRY.md": {
        "monotonic_counters": [re.compile(r"\*\*Next Available Feature Number:\*\*\s*(F\d{4})")],
        "tables": {
            "Active Features": {"order": ("id_asc",)},
            "Retired Features": {"order": ("date_desc", "Retired Date")},
            "Planned (Reserved IDs)": {"order": ("id_asc",)},
            "Archived Features": {"order": ("date_desc", "Archived Date")},
            "Legacy Mapping": {"order": ("id_asc",)},
        },
        "exclusive_groups": [
            ["Active Features", "Retired Features", "Planned (Reserved IDs)", "Archived Features"],
        ],
    },
    "ROADMAP.md": {
        "monotonic_counters": [],
        "tables": {
            "Now": {"order": ("manual",)},
            "Next": {"order": ("manual",)},
            "Later": {"order": ("manual",)},
            "Abandoned": {"order": ("manual",)},
            "Completed": {"order": ("manual",)},
        },
        "exclusive_groups": [["Now", "Next", "Later", "Abandoned", "Completed"]],
    },
}


@dataclass
class Table:
    columns: list[str]
    rows: dict[str, dict[str, str]]  # key -> {column: cell}
    key_order: list[str]


@dataclass
class Section:
    heading: str  # heading text ("" for the preamble)
    heading_line: str
    pre_prose: list[str]
    table: Table | None
    post_prose: list[str]


@dataclass
class TrackerMergeResult:
    merged_text: str
    conflicts: list[Conflict] = dataclass_field(default_factory=list)
    warnings: list[dict[str, Any]] = dataclass_field(default_factory=list)
    stats: dict[str, int] = dataclass_field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
# Parsing and rendering
# ──────────────────────────────────────────────────────────────


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def _is_separator_row(line: str) -> bool:
    return bool(re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+", line.strip()))


def _row_key(cells: list[str]) -> str | None:
    match = FEATURE_ID_RE.search(cells[0]) if cells else None
    return match.group(0) if match else None


def parse_tracker(text: str, basename: str) -> list[Section]:
    """Split a tracker into sections, each with at most one keyed table."""
    lines = text.splitlines()
    sections: list[Section] = []
    current = Section(heading="", heading_line="", pre_prose=[], table=None, post_prose=[])

    index = 0
    while index < len(lines):
        line = lines[index]
        heading = HEADING_RE.match(line)
        if heading and len(heading.group(1)) <= 2 and index > 0:
            sections.append(current)
            current = Section(
                heading=heading.group(2).strip(),
                heading_line=line,
                pre_prose=[],
                table=None,
                post_prose=[],
            )
            index += 1
            continue
        if heading and index == 0:
            current = Section(
                heading=heading.group(2).strip(),
                heading_line=line,
                pre_prose=[],
                table=None,
                post_prose=[],
            )
            index += 1
            continue

        if _is_table_line(line):
            block: list[str] = []
            while index < len(lines) and _is_table_line(lines[index]):
                block.append(lines[index])
                index += 1
            if current.table is not None:
                raise TrackerFormatError(
                    f"{basename}: section `{current.heading}` has more than one table; "
                    "tracker merge supports one keyed table per section"
                )
            current.table = _parse_table(block, current.heading, basename)
            continue

        if current.table is None:
            current.pre_prose.append(line)
        else:
            current.post_prose.append(line)
        index += 1

    sections.append(current)
    return sections


class TrackerFormatError(RuntimeError):
    pass


def _parse_table(block: list[str], heading: str, basename: str) -> Table:
    if len(block) < 2 or not _is_separator_row(block[1]):
        raise TrackerFormatError(
            f"{basename}: table in section `{heading}` lacks a header/separator row"
        )
    columns = _split_row(block[0])
    rows: dict[str, dict[str, str]] = {}
    key_order: list[str] = []
    for line in block[2:]:
        cells = _split_row(line)
        if len(cells) != len(columns):
            cells = (cells + [""] * len(columns))[: len(columns)]
        key = _row_key(cells)
        if key is None:
            raise TrackerFormatError(
                f"{basename}: row in `{heading}` has no identifiable feature ID "
                f"in its key column: {line.strip()}"
            )
        if key in rows:
            raise TrackerFormatError(
                f"{basename}: duplicate feature ID `{key}` in section `{heading}`"
            )
        rows[key] = dict(zip(columns, cells))
        key_order.append(key)
    return Table(columns=columns, rows=rows, key_order=key_order)


def _render_table(table: Table, order: list[str]) -> list[str]:
    lines = [
        "| " + " | ".join(table.columns) + " |",
        "|" + "|".join("-" * (len(col) + 2) for col in table.columns) + "|",
    ]
    for key in order:
        row = table.rows[key]
        lines.append("| " + " | ".join(row.get(col, "") for col in table.columns) + " |")
    return lines


def render_sections(sections: list[Section], orders: dict[str, list[str]]) -> str:
    out: list[str] = []
    for section in sections:
        if section.heading_line:
            out.append(section.heading_line)
        out.extend(section.pre_prose)
        if section.table is not None:
            out.extend(_render_table(section.table, orders.get(section.heading, section.table.key_order)))
        out.extend(section.post_prose)
    text = "\n".join(out)
    return text if text.endswith("\n") else text + "\n"


# ──────────────────────────────────────────────────────────────
# Ordering rules
# ──────────────────────────────────────────────────────────────


def _sorted_order(table: Table, rule: tuple, keys: set[str]) -> list[str] | None:
    """Deterministic order for sortable tables; None means manual."""
    if rule[0] == "id_asc":
        return sorted(keys)
    if rule[0] == "date_desc":
        date_column = rule[1]

        def sort_key(key: str) -> tuple[str, str]:
            return (table.rows[key].get(date_column, ""), key)

        return sorted(keys, key=sort_key, reverse=True)
    return None


def _merge_manual_order(
    base_keys: list[str],
    ours_keys: list[str],
    theirs_keys: list[str],
    surviving: set[str],
) -> list[str] | None:
    """Three-way order merge for manual tables; None on a real double reorder."""
    base = [k for k in base_keys if k in surviving]
    ours = [k for k in ours_keys if k in surviving]
    theirs = [k for k in theirs_keys if k in surviving]

    def with_missing_appended(order: list[str]) -> list[str]:
        return order + sorted(surviving - set(order), reverse=True)

    if ours == theirs:
        return with_missing_appended(ours)
    if ours == base:
        return with_missing_appended(theirs)
    if theirs == base:
        return with_missing_appended(ours)

    # Both changed: allowed only when both sides purely *added* rows —
    # the common rows must appear in the same relative order everywhere.
    def common_subsequence_intact(side: list[str]) -> bool:
        side_common = [k for k in side if k in set(base)]
        base_common = [k for k in base if k in set(side)]
        return side_common == base_common

    if not (common_subsequence_intact(ours) and common_subsequence_intact(theirs)):
        return None

    result = list(ours)
    in_result = set(result)
    for position, key in enumerate(theirs):
        if key in in_result:
            continue
        # Insert after the nearest preceding theirs-row already present.
        anchor = None
        for prior in reversed(theirs[:position]):
            if prior in in_result:
                anchor = prior
                break
        if anchor is None:
            # Head insertion: place before the first row ours shares with theirs
            # (ours' own head insertions stay first).
            insert_at = next(
                (i for i, k in enumerate(result) if k in set(theirs)), len(result)
            )
        else:
            insert_at = result.index(anchor) + 1
        result.insert(insert_at, key)
        in_result.add(key)
    return with_missing_appended(result)


# ──────────────────────────────────────────────────────────────
# Merge
# ──────────────────────────────────────────────────────────────


def _pm_conflict(path: str, record_id: str | None, base: Any, ours: Any, theirs: Any, kind: str, message: str) -> Conflict:
    return Conflict(
        kind=kind,
        record_id=record_id,
        field=path or None,
        base=base,
        ours=ours,
        theirs=theirs,
        owning_role="product-manager",
        message=message,
    )


def _apply_counters(texts: dict[str, str], patterns: list[re.Pattern[str]]) -> dict[str, str]:
    """Rewrite monotonic counters to the max across sides before merging."""
    for pattern in patterns:
        values = [
            match.group(1)
            for text in texts.values()
            for match in [pattern.search(text)]
            if match
        ]
        if not values:
            continue
        maximum = max(values)
        texts = {
            label: pattern.sub(
                lambda m: m.group(0).replace(m.group(1), maximum), text, count=1
            )
            for label, text in texts.items()
        }
    return texts


def _merge_prose(
    path: str,
    base: list[str],
    ours: list[str],
    theirs: list[str],
    conflicts: list[Conflict],
) -> list[str]:
    if ours == theirs:
        return ours
    if ours == base:
        return theirs
    if theirs == base:
        return ours
    # Append-tolerant: both sides only appended below the shared base block.
    if base == ours[: len(base)] and base == theirs[: len(base)]:
        return base + ours[len(base):] + theirs[len(base):]
    conflicts.append(
        _pm_conflict(
            path,
            None,
            "\n".join(base),
            "\n".join(ours),
            "\n".join(theirs),
            "DivergentUpdate",
            "prose changed on both sides; merge by hand (PM owns tracker prose)",
        )
    )
    return ours


def merge_tracker_documents(
    base_text: str,
    ours_text: str,
    theirs_text: str,
    basename: str,
) -> TrackerMergeResult:
    config = TRACKER_CONFIGS.get(basename)
    if config is None:
        raise TrackerFormatError(
            f"no tracker merge configuration for `{basename}` — refusing a silent "
            "text merge (known trackers: " + ", ".join(sorted(TRACKER_CONFIGS)) + ")"
        )

    texts = _apply_counters(
        {"base": base_text, "ours": ours_text, "theirs": theirs_text},
        config["monotonic_counters"],
    )
    parsed = {label: parse_tracker(text, basename) for label, text in texts.items()}
    by_heading = {
        label: {section.heading: section for section in sections}
        for label, sections in parsed.items()
    }

    conflicts: list[Conflict] = []
    engine = MergeEngine(basename)

    # Section sequence: adopt a changed side's sequence (one-side rule).
    sequences = {label: [s.heading for s in sections] for label, sections in parsed.items()}
    if sequences["ours"] == sequences["base"]:
        section_order = sequences["theirs"]
    elif sequences["theirs"] == sequences["base"] or sequences["ours"] == sequences["theirs"]:
        section_order = sequences["ours"]
    else:
        conflicts.append(
            _pm_conflict(
                "<sections>",
                None,
                sequences["base"],
                sequences["ours"],
                sequences["theirs"],
                "OrderedListConflict",
                "section structure changed on both sides",
            )
        )
        section_order = sequences["ours"]

    merged_sections: list[Section] = []
    orders: dict[str, list[str]] = {}
    stats = {"rows_base": 0, "rows_ours": 0, "rows_theirs": 0, "rows_merged": 0}

    for heading in section_order:
        versions = {
            label: by_heading[label].get(heading) for label in ("base", "ours", "theirs")
        }
        present = {label: section for label, section in versions.items() if section is not None}
        exemplar = versions["ours"] or versions["theirs"] or versions["base"]

        # Section added/removed on one side only follows the one-side rule.
        if versions["base"] is None and len(present) == 1:
            merged_sections.append(next(iter(present.values())))
            continue
        if versions["base"] is not None and (versions["ours"] is None or versions["theirs"] is None):
            survivor = versions["ours"] or versions["theirs"]
            base_section = versions["base"]
            if survivor is None:
                continue  # deleted on both sides
            if _section_equal(survivor, base_section):
                continue  # deleted on one side, unchanged on the other
            conflicts.append(
                _pm_conflict(
                    heading,
                    None,
                    "<section>",
                    "<deleted>" if versions["ours"] is None else "<changed>",
                    "<deleted>" if versions["theirs"] is None else "<changed>",
                    "DeleteVsUpdate",
                    f"section `{heading}` deleted on one side and changed on the other",
                )
            )
            merged_sections.append(survivor)
            continue

        base_s, ours_s, theirs_s = versions["base"], versions["ours"], versions["theirs"]
        assert ours_s is not None and theirs_s is not None

        merged = Section(
            heading=heading,
            heading_line=exemplar.heading_line,
            pre_prose=_merge_prose(
                f"{heading}#prose",
                base_s.pre_prose if base_s else [],
                ours_s.pre_prose,
                theirs_s.pre_prose,
                conflicts,
            ),
            table=None,
            post_prose=_merge_prose(
                f"{heading}#notes",
                base_s.post_prose if base_s else [],
                ours_s.post_prose,
                theirs_s.post_prose,
                conflicts,
            ),
        )

        tables = {
            label: section.table if section else None for label, section in versions.items()
        }
        if any(tables.values()):
            merged.table, order, table_conflicts, table_stats = _merge_table(
                heading, tables, config, engine
            )
            conflicts.extend(table_conflicts)
            if merged.table is not None:
                orders[heading] = order
            for key, value in table_stats.items():
                stats[key] += value

        merged_sections.append(merged)

    conflicts.extend(engine.conflicts)
    _check_exclusive_groups(merged_sections, config, conflicts)

    merged_text = render_sections(merged_sections, orders)
    result = TrackerMergeResult(merged_text=merged_text, conflicts=conflicts)
    result.stats = {**stats, "conflicts": len(conflicts)}
    return result


def _section_equal(a: Section, b: Section) -> bool:
    return (
        a.pre_prose == b.pre_prose
        and a.post_prose == b.post_prose
        and _table_state(a.table) == _table_state(b.table)
    )


def _table_state(table: Table | None) -> Any:
    if table is None:
        return None
    return (table.columns, table.rows, table.key_order)


def _merge_table(
    heading: str,
    tables: dict[str, Table | None],
    config: dict[str, Any],
    engine: MergeEngine,
) -> tuple[Table | None, list[str], list[Conflict], dict[str, int]]:
    conflicts: list[Conflict] = []
    table_config = config["tables"].get(heading)
    if table_config is None:
        raise TrackerFormatError(
            f"table in unconfigured section `{heading}` — add it to TRACKER_CONFIGS "
            "(no silent text-merge fallback)"
        )

    base_t = tables["base"] or Table(columns=[], rows={}, key_order=[])
    ours_t = tables["ours"]
    theirs_t = tables["theirs"]
    if ours_t is None or theirs_t is None:
        conflicts.append(
            _pm_conflict(
                heading,
                None,
                "<table>",
                "<missing>" if ours_t is None else "<present>",
                "<missing>" if theirs_t is None else "<present>",
                "DeleteVsUpdate",
                f"table `{heading}` missing on one side",
            )
        )
        survivor = ours_t or theirs_t
        return survivor, survivor.key_order if survivor else [], conflicts, {}

    if not base_t.columns:
        base_t = Table(columns=ours_t.columns, rows={}, key_order=[])
    if not (base_t.columns == ours_t.columns == theirs_t.columns):
        conflicts.append(
            _pm_conflict(
                heading,
                None,
                base_t.columns,
                ours_t.columns,
                theirs_t.columns,
                "DivergentUpdate",
                f"table `{heading}` column structure differs across versions",
            )
        )
        return ours_t, ours_t.key_order, conflicts, {}

    merged_rows: dict[str, dict[str, str]] = {}
    all_keys = list(dict.fromkeys([*base_t.key_order, *ours_t.key_order, *theirs_t.key_order]))
    for key in all_keys:
        value = engine._merge_value(
            f"{heading}[{key}]",
            None,
            key,
            base_t.rows.get(key, _MISSING),
            ours_t.rows.get(key, _MISSING),
            theirs_t.rows.get(key, _MISSING),
        )
        if value is not _MISSING:
            merged_rows[key] = value

    merged_table = Table(
        columns=ours_t.columns, rows=merged_rows, key_order=list(merged_rows)
    )
    surviving = set(merged_rows)
    order = _sorted_order(merged_table, table_config["order"], surviving)
    if order is None:
        order = _merge_manual_order(
            base_t.key_order, ours_t.key_order, theirs_t.key_order, surviving
        )
        if order is None:
            conflicts.append(
                _pm_conflict(
                    heading,
                    None,
                    base_t.key_order,
                    ours_t.key_order,
                    theirs_t.key_order,
                    "OrderedListConflict",
                    f"manually ordered table `{heading}` reordered on both sides",
                )
            )
            order = merged_table.key_order

    stats = {
        "rows_base": len(base_t.rows),
        "rows_ours": len(ours_t.rows),
        "rows_theirs": len(theirs_t.rows),
        "rows_merged": len(merged_rows),
    }
    return merged_table, order, conflicts, stats


def _check_exclusive_groups(
    sections: list[Section],
    config: dict[str, Any],
    conflicts: list[Conflict],
) -> None:
    by_heading = {section.heading: section for section in sections}
    for group in config.get("exclusive_groups", []):
        locations: dict[str, list[str]] = {}
        for heading in group:
            section = by_heading.get(heading)
            if section and section.table:
                for key in section.table.rows:
                    locations.setdefault(key, []).append(heading)
        for key, headings in sorted(locations.items()):
            if len(headings) > 1:
                conflicts.append(
                    _pm_conflict(
                        f"section:{key}",
                        key,
                        None,
                        headings,
                        headings,
                        "DivergentUpdate",
                        f"`{key}` appears in more than one exclusive section after "
                        f"the merge ({', '.join(headings)}) — section membership is "
                        "a field and the two sides disagree",
                    )
                )


def tracker_semantic_diff(old_text: str, new_text: str, basename: str) -> dict[str, list[str]]:
    """Row-level diff between two tracker versions (for replay evidence)."""
    old_sections = {s.heading: s for s in parse_tracker(old_text, basename)}
    new_sections = {s.heading: s for s in parse_tracker(new_text, basename)}

    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []
    for heading in sorted(set(old_sections) | set(new_sections)):
        old_table = old_sections.get(heading).table if heading in old_sections else None
        new_table = new_sections.get(heading).table if heading in new_sections else None
        old_rows = old_table.rows if old_table else {}
        new_rows = new_table.rows if new_table else {}
        added.extend(f"{heading}[{k}]" for k in sorted(set(new_rows) - set(old_rows)))
        removed.extend(f"{heading}[{k}]" for k in sorted(set(old_rows) - set(new_rows)))
        changed.extend(
            f"{heading}[{k}]"
            for k in sorted(set(old_rows) & set(new_rows))
            if old_rows[k] != new_rows[k]
        )
    return {"added": added, "removed": removed, "changed": changed, "meta": []}
