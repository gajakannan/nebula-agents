#!/usr/bin/env python3
"""
Tracker Validation Script

Validates planning tracker consistency across:
- {NEBULA_PRODUCT_ROOT}/planning-mds/features/REGISTRY.md
- {NEBULA_PRODUCT_ROOT}/planning-mds/features/ROADMAP.md
- {NEBULA_PRODUCT_ROOT}/planning-mds/features/STORY-INDEX.md
- {NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md
- feature STATUS closeout signoff governance for Done/Archived features

Usage:
    python3 agents/product-manager/scripts/validate-trackers.py
    python3 agents/product-manager/scripts/validate-trackers.py --features-dir {NEBULA_PRODUCT_ROOT}/planning-mds/features --blueprint {NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md
    python3 agents/product-manager/scripts/validate-trackers.py --feature F0038 --run-id 2026-06-30-dbc93ab5
    python3 agents/product-manager/scripts/validate-trackers.py --all-feature-evidence
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402


FEATURE_ID_RE = re.compile(r"F\d{4}")
STRICT_STORY_FILE_RE = re.compile(r"^F\d{4}-S\d{4}-.+\.md$")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}$")

ROLE_ALIAS_MAP = {
    "qe": "qualityengineer",
    "qualityassurance": "qualityengineer",
    "qualityengineer": "qualityengineer",
    "codereviewer": "codereviewer",
    "reviewer": "codereviewer",
    "security": "securityreviewer",
    "securityreviewer": "securityreviewer",
    "devops": "devops",
    "architect": "architect",
}

BASELINE_REQUIRED_SIGNOFF_ROLES = {
    "qualityengineer": "Quality Engineer",
    "codereviewer": "Code Reviewer",
}


def _strip_code(value: str) -> str:
    return value.strip().strip("`")


def _normalize_role(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _canonical_role(value: str) -> str:
    normalized = _normalize_role(value)
    return ROLE_ALIAS_MAP.get(normalized, normalized)


def _extract_first_section(content: str, headings: Sequence[str]) -> str:
    for heading in headings:
        section = _extract_section(content, heading)
        if section:
            return section
    return ""


def _is_required_flag(value: str) -> bool:
    normalized = value.strip().casefold()
    return normalized in {
        "yes",
        "y",
        "true",
        "required",
        "must",
        "[x]",
        "x",
        "✅",
    }


def _is_pass_verdict(value: str) -> bool:
    normalized = value.strip().casefold()
    return normalized in {"pass", "approved"}


def _has_meaningful_value(value: str) -> bool:
    normalized = value.strip().casefold()
    return normalized not in {"", "-", "n/a", "na", "tbd", "none"}


def _extract_section(content: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(content)
    if not match:
        return ""

    start = match.end()
    next_heading = re.search(r"^##\s+", content[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(content)
    return content[start:end]


def _parse_table(section: str) -> List[Dict[str, str]]:
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        return []

    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows: List[Dict[str, str]] = []

    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append({headers[i]: cells[i] for i in range(len(headers))})

    return rows


def _parse_markdown_tables(content: str) -> List[List[Dict[str, str]]]:
    tables: List[List[Dict[str, str]]] = []
    current: List[str] = []

    def flush() -> None:
        if not current:
            return
        parsed = _parse_table("\n".join(current))
        if parsed:
            tables.append(parsed)
        current.clear()

    for line in content.splitlines():
        if line.strip().startswith("|"):
            current.append(line)
        else:
            flush()
    flush()
    return tables


def _extract_link(markdown: str) -> Optional[str]:
    match = re.search(r"\]\(([^)]+)\)", markdown)
    return match.group(1).strip() if match else None


def _extract_feature_id(text: str) -> Optional[str]:
    match = FEATURE_ID_RE.search(text)
    return match.group(0) if match else None


@dataclass
class Issue:
    severity: str  # ERROR | WARNING
    location: str
    message: str


@dataclass
class RegistryEntry:
    feature_id: str
    name: str
    status: str
    phase: str
    folder: str


@dataclass
class RoadmapEntry:
    section: str
    feature_id: str
    raw_feature: str
    link: Optional[str]


@dataclass
class StoryStatusRow:
    story_id: str
    status: str


class TrackerValidator:
    def __init__(self, features_dir: Path, blueprint_path: Path):
        self.features_dir = features_dir
        self.blueprint_path = blueprint_path
        self.root_dir = features_dir.parent
        self.registry_path = features_dir / "REGISTRY.md"
        self.roadmap_path = features_dir / "ROADMAP.md"
        self.story_index_path = features_dir / "STORY-INDEX.md"
        self.issues: List[Issue] = []

        self.registry_active: Dict[str, RegistryEntry] = {}
        self.registry_planned: Dict[str, RegistryEntry] = {}
        self.registry_archived: Dict[str, RegistryEntry] = {}

    def add_error(self, location: str, message: str) -> None:
        self.issues.append(Issue("ERROR", location, message))

    def add_warning(self, location: str, message: str) -> None:
        self.issues.append(Issue("WARNING", location, message))

    def read_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception as exc:
            self.add_error(str(path), f"Failed to read file: {exc}")
            return ""

    def resolve_feature_path(self, raw_path: str) -> Optional[Path]:
        cleaned = _strip_code(raw_path)
        if not cleaned or cleaned.upper() == "TBD":
            return None

        if cleaned.startswith("{NEBULA_PRODUCT_ROOT}/planning-mds/features/"):
            rel = cleaned[len("{NEBULA_PRODUCT_ROOT}/planning-mds/features/") :]
            return self.features_dir / rel
        if cleaned.startswith("./"):
            return self.features_dir / cleaned[2:]
        return self.features_dir / cleaned

    def load_registry(self) -> None:
        content = self.read_file(self.registry_path)
        if not content:
            return

        sections = {
            "Active Features": self.registry_active,
            "Planned (Reserved IDs)": self.registry_planned,
            "Archived Features": self.registry_archived,
        }

        for heading, bucket in sections.items():
            rows = _parse_table(_extract_section(content, heading))
            if not rows and heading not in {"Planned (Reserved IDs)", "Active Features", "Archived Features"}:
                self.add_error(str(self.registry_path), f"Missing or malformed table for section: {heading}")

            for row in rows:
                feature_id = row.get("Feature ID", "").strip()
                if not FEATURE_ID_RE.fullmatch(feature_id):
                    self.add_error(str(self.registry_path), f"Invalid feature ID in {heading}: {feature_id!r}")
                    continue
                bucket[feature_id] = RegistryEntry(
                    feature_id=feature_id,
                    name=row.get("Name", "").strip(),
                    status=row.get("Status", "").strip(),
                    phase=row.get("Phase", "").strip(),
                    folder=_strip_code(row.get("Folder", "").strip()),
                )

        for feature_id, entry in self.registry_active.items():
            resolved = self.resolve_feature_path(entry.folder)
            if resolved is None:
                self.add_error(
                    str(self.registry_path),
                    f"Active feature {feature_id} has invalid folder path: {entry.folder!r}",
                )
                continue
            if entry.folder.startswith("archive/"):
                self.add_error(
                    str(self.registry_path),
                    f"Active feature {feature_id} points to archive path: {entry.folder}",
                )
            if not resolved.exists():
                self.add_error(str(self.registry_path), f"Active feature folder does not exist: {resolved}")
            self._validate_status_doc(feature_id, resolved, registry_state="Active")

        for feature_id, entry in self.registry_archived.items():
            resolved = self.resolve_feature_path(entry.folder)
            if resolved is None:
                self.add_error(
                    str(self.registry_path),
                    f"Archived feature {feature_id} has invalid folder path: {entry.folder!r}",
                )
                continue
            if not entry.folder.startswith("archive/"):
                self.add_error(
                    str(self.registry_path),
                    f"Archived feature {feature_id} must use archive/ path: {entry.folder}",
                )
            if not resolved.exists():
                self.add_error(str(self.registry_path), f"Archived feature folder does not exist: {resolved}")
            self._validate_status_doc(feature_id, resolved, registry_state="Archived")

    def _validate_status_doc(self, feature_id: str, feature_folder: Path, registry_state: str) -> None:
        status_file = feature_folder / "STATUS.md"
        if not status_file.exists():
            self.add_error(str(status_file), f"Missing STATUS.md for {feature_id}")
            return

        content = self.read_file(status_file)
        if not content:
            return

        status_match = re.search(r"\*\*Overall Status:\*\*\s*(.+)", content)
        if not status_match:
            self.add_error(str(status_file), "Missing '**Overall Status:**' line")
            return

        overall_status = status_match.group(1).strip()
        if registry_state == "Archived" and not self._is_terminal_status(overall_status):
            self.add_error(
                str(status_file),
                (
                    f"{feature_id} is listed under Archived Features in REGISTRY.md but "
                    f"STATUS.md has non-terminal Overall Status: {overall_status!r}"
                ),
            )

        if self._requires_done_archive_closeout(overall_status):
            self._validate_signoff_sections(feature_id, status_file, content)

    def _is_terminal_status(self, overall_status: str) -> bool:
        normalized = overall_status.casefold()
        return any(
            token in normalized
            for token in (
                "done",
                "archived",
                "abandoned",
                "superseded",
                "historical",
            )
        )

    def _requires_done_archive_closeout(self, overall_status: str) -> bool:
        normalized = overall_status.casefold()
        return "done" in normalized or "archived" in normalized

    def _validate_signoff_sections(self, feature_id: str, status_file: Path, content: str) -> None:
        required_section = _extract_first_section(
            content,
            [
                "Required Role Matrix",
                "Required Signoff Roles",
                "Required Signoff Roles (Set in Planning)",
            ],
        )
        if not required_section:
            self.add_error(
                str(status_file),
                f"{feature_id} is Done/Archived but missing 'Required Role Matrix' / 'Required Signoff Roles' section",
            )
            return

        required_rows = _parse_table(required_section)
        if not required_rows:
            self.add_error(
                str(status_file),
                f"{feature_id} is Done/Archived but required role/signoff table is missing or malformed",
            )
            return

        required_roles: Dict[str, str] = {}
        for row in required_rows:
            role = row.get("Role", "").strip()
            if not role:
                continue
            required_flag = row.get("Required", "").strip()
            if _is_required_flag(required_flag):
                canonical = _canonical_role(role)
                required_roles[canonical] = role

        if not required_roles:
            self.add_error(
                str(status_file),
                f"{feature_id} is Done/Archived but no required signoff roles are marked 'Yes'",
            )
            return

        for canonical, label in BASELINE_REQUIRED_SIGNOFF_ROLES.items():
            if canonical not in required_roles:
                self.add_error(
                    str(status_file),
                    f"{feature_id} is Done/Archived but baseline required signoff role is missing: {label}",
                )

        story_rows = self._extract_story_status_rows_from_status(content, status_file)
        story_ids = [row.story_id for row in story_rows]
        if not story_ids:
            self.add_error(
                str(status_file),
                f"{feature_id} is Done/Archived but no story IDs were found in Story Checklist/Stories table",
            )
            return
        self._validate_completed_story_statuses(feature_id, status_file, content, story_rows)

        provenance_rows = self._extract_story_provenance_rows(content)
        if not provenance_rows:
            self.add_error(
                str(status_file),
                f"{feature_id} is Done/Archived but missing 'Story Signoff Provenance' section",
            )
            return

        passing_pairs: Dict[Tuple[str, str], bool] = {}
        for row in provenance_rows:
            story_cell = row.get("Story", "").strip()
            story_match = re.search(r"F\d{4}-S\d{4}", story_cell)
            if not story_match:
                continue

            story_id = story_match.group(0)
            role = row.get("Role", "").strip()
            if not role:
                continue

            canonical = _canonical_role(role)
            verdict = row.get("Verdict", "").strip()
            reviewer = row.get("Reviewer", "").strip()
            evidence = row.get("Evidence", "").strip()
            date_value = row.get("Date", "").strip()

            if _is_pass_verdict(verdict):
                if not reviewer:
                    self.add_error(
                        str(status_file),
                        f"Story provenance PASS row for {story_id} role '{role}' is missing reviewer",
                    )
                    continue
                if not _has_meaningful_value(evidence):
                    self.add_error(
                        str(status_file),
                        f"Story provenance PASS row for {story_id} role '{role}' is missing evidence",
                    )
                    continue
                if "agents/" in evidence.casefold():
                    self.add_error(
                        str(status_file),
                        (
                            f"Story provenance PASS row for {story_id} role '{role}' references "
                            "agents/ in evidence; use solution artifacts ({NEBULA_PRODUCT_ROOT}/planning-mds/, code, tests, CI outputs)"
                        ),
                    )
                    continue
                if not ISO_DATE_RE.fullmatch(date_value):
                    self.add_error(
                        str(status_file),
                        f"Story provenance PASS row for {story_id} role '{role}' has invalid date: {date_value!r}",
                    )
                    continue
                passing_pairs[(story_id, canonical)] = True

        for story_id in story_ids:
            for canonical, display_role in required_roles.items():
                if not passing_pairs.get((story_id, canonical), False):
                    self.add_error(
                        str(status_file),
                        f"Required role '{display_role}' is missing PASS/APPROVED provenance for story {story_id}",
                    )

    def _extract_story_status_rows_from_status(self, content: str, status_file: Path) -> List[StoryStatusRow]:
        section = _extract_first_section(content, ["Story Checklist", "Stories"])
        if not section:
            return []

        rows = _parse_table(section)
        story_rows: List[StoryStatusRow] = []
        seen = set()

        for row in rows:
            story_cell = row.get("Story", "").strip()
            match = re.search(r"F\d{4}-S\d{4}", story_cell)
            if not match:
                continue
            story_id = match.group(0)
            if story_id not in seen:
                story_rows.append(StoryStatusRow(story_id=story_id, status=row.get("Status", "").strip()))
                seen.add(story_id)

        if not story_rows:
            self.add_warning(str(status_file), "No parseable story IDs found in story status table")

        return story_rows

    def _validate_completed_story_statuses(
        self,
        feature_id: str,
        status_file: Path,
        content: str,
        story_rows: Sequence[StoryStatusRow],
    ) -> None:
        for row in story_rows:
            if self._is_completed_story_status(row.status):
                continue
            if self._is_deferred_or_rehomed_story_status(row.status):
                if self._has_deferred_or_rehomed_record(content, row.story_id):
                    continue
                self.add_error(
                    str(status_file),
                    (
                        f"{feature_id} is Done/Archived but story {row.story_id} has status "
                        f"{row.status!r} without a matching deferred/rehome record"
                    ),
                )
                continue
            self.add_error(
                str(status_file),
                f"{feature_id} is Done/Archived but story {row.story_id} has non-completed status: {row.status!r}",
            )

    def _is_completed_story_status(self, value: str) -> bool:
        normalized = re.sub(r"\[[ xX]\]", "", value).strip().casefold()
        return any(
            token in normalized
            for token in ("done", "complete", "completed", "closed", "archived", "approved", "implemented")
        )

    def _is_deferred_or_rehomed_story_status(self, value: str) -> bool:
        normalized = value.casefold()
        return any(token in normalized for token in ("deferred", "rehomed", "re-homed", "promoted", "superseded"))

    def _has_deferred_or_rehomed_record(self, content: str, story_id: str) -> bool:
        sections = [
            "Deferred Non-Blocking Follow-ups",
            "Deferred Follow-ups",
            "Deferred Scope",
            "Orphaned Story Review",
        ]
        for section_name in sections:
            section = _extract_section(content, section_name)
            if story_id in section and re.search(r"F\d{4}|https?://|\[[^\]]+\]\([^)]+\)", section):
                return True
        return False

    def _extract_story_provenance_rows(self, content: str) -> List[Dict[str, str]]:
        required_columns = {"Story", "Role", "Reviewer", "Verdict", "Evidence", "Date"}
        rows: List[Dict[str, str]] = []
        for table in _parse_markdown_tables(content):
            if table and required_columns.issubset(table[0].keys()):
                rows.extend(table)
        return rows

    def load_roadmap(self) -> List[RoadmapEntry]:
        content = self.read_file(self.roadmap_path)
        if not content:
            return []

        entries: List[RoadmapEntry] = []
        sections = ["Now", "Next", "Later", "Completed"]

        for section in sections:
            rows = _parse_table(_extract_section(content, section))
            for row in rows:
                raw_feature = row.get("Feature", "").strip()
                feature_id = _extract_feature_id(raw_feature or row.get("Feature ID", ""))
                if not feature_id:
                    self.add_warning(
                        str(self.roadmap_path),
                        f"Skipping roadmap row in '{section}' without feature ID: {raw_feature!r}",
                    )
                    continue
                entry = RoadmapEntry(
                    section=section,
                    feature_id=feature_id,
                    raw_feature=raw_feature,
                    link=_extract_link(raw_feature),
                )
                entries.append(entry)

        self.validate_roadmap_entries(entries)
        return entries

    def validate_roadmap_entries(self, entries: Sequence[RoadmapEntry]) -> None:
        seen: Dict[str, str] = {}
        for entry in entries:
            if entry.feature_id in seen:
                self.add_error(
                    str(self.roadmap_path),
                    f"Feature {entry.feature_id} appears in multiple roadmap sections ({seen[entry.feature_id]} and {entry.section})",
                )
            else:
                seen[entry.feature_id] = entry.section

            if entry.link:
                resolved = self.resolve_feature_path(entry.link)
                if resolved is None:
                    self.add_error(
                        str(self.roadmap_path),
                        f"Roadmap link for {entry.feature_id} in {entry.section} is invalid: {entry.link}",
                    )
                elif not resolved.exists():
                    self.add_error(
                        str(self.roadmap_path),
                        f"Roadmap link target missing for {entry.feature_id}: {resolved}",
                    )

                if entry.section in {"Now", "Next", "Later"} and entry.link.startswith("./archive/"):
                    self.add_error(
                        str(self.roadmap_path),
                        f"Feature {entry.feature_id} in {entry.section} should not link to archive path",
                    )

            if entry.feature_id in self.registry_archived and entry.section != "Completed":
                self.add_error(
                    str(self.roadmap_path),
                    f"Archived feature {entry.feature_id} appears in roadmap section '{entry.section}'",
                )

        active_ids = set(self.registry_active.keys())
        roadmap_ids = {entry.feature_id for entry in entries}
        for feature_id in sorted(active_ids - roadmap_ids):
            self.add_warning(
                str(self.roadmap_path),
                f"Active feature {feature_id} is missing from roadmap Now/Next/Later/Completed sections",
            )

    def collect_story_files(self) -> Tuple[List[Path], List[str]]:
        story_files: List[Path] = []
        story_ids: List[str] = []

        for path in sorted(self.features_dir.rglob("*.md")):
            if path.name in {"REGISTRY.md", "ROADMAP.md", "STORY-INDEX.md", "TRACKER-GOVERNANCE.md"}:
                continue

            if STRICT_STORY_FILE_RE.match(path.name):
                content = self.read_file(path)
                if "**Story ID:**" not in content:
                    self.add_error(
                        str(path),
                        "Filename matches story pattern but file is missing '**Story ID:**' header",
                    )
                    continue

                prefix = "-".join(path.stem.split("-")[:2])
                story_id_match = re.search(r"\*\*Story ID:\*\*\s*(F\d{4}-S\d{4})", content)
                if not story_id_match:
                    self.add_error(str(path), "Cannot parse Story ID from story file")
                    continue
                story_id = story_id_match.group(1)
                if story_id != prefix:
                    self.add_error(
                        str(path),
                        f"Story ID {story_id} does not match filename prefix {prefix}",
                    )
                story_files.append(path)
                story_ids.append(story_id)
            elif re.match(r"^F\d{4}-S\d{4}", path.name):
                self.add_error(
                    str(path),
                    "Non-story document starts with F{NNNN}-S{NNNN}; rename to avoid STORY-INDEX drift",
                )

        duplicate_ids = [story_id for story_id in sorted(set(story_ids)) if story_ids.count(story_id) > 1]
        for story_id in duplicate_ids:
            self.add_error(str(self.features_dir), f"Duplicate story ID detected: {story_id}")

        return story_files, story_ids

    def validate_story_index(self, story_files: Sequence[Path], story_ids: Sequence[str]) -> None:
        content = self.read_file(self.story_index_path)
        if not content:
            return

        total_match = re.search(r"\*\*Total Stories:\*\*\s*(\d+)", content)
        if not total_match:
            self.add_error(str(self.story_index_path), "Missing '**Total Stories:**' header")
        else:
            total = int(total_match.group(1))
            if total != len(story_files):
                self.add_error(
                    str(self.story_index_path),
                    f"Total stories mismatch: index says {total}, filesystem has {len(story_files)}",
                )

        link_matches = re.findall(r"\[(F\d{4}-S\d{4})\]\(\./([^)]+)\)", content)
        linked_ids = [item[0] for item in link_matches]
        linked_paths = [item[1] for item in link_matches]

        if len(linked_ids) != len(story_files):
            self.add_error(
                str(self.story_index_path),
                f"Story link count mismatch: index has {len(linked_ids)} entries, filesystem has {len(story_files)}",
            )

        expected_ids = sorted(story_ids)
        if sorted(linked_ids) != expected_ids:
            missing = sorted(set(expected_ids) - set(linked_ids))
            extra = sorted(set(linked_ids) - set(expected_ids))
            if missing:
                self.add_error(str(self.story_index_path), f"Missing story IDs in index: {', '.join(missing)}")
            if extra:
                self.add_error(str(self.story_index_path), f"Unexpected story IDs in index: {', '.join(extra)}")

        for rel in linked_paths:
            linked_file = self.features_dir / rel
            if not linked_file.exists():
                self.add_error(str(self.story_index_path), f"Story index link target missing: {rel}")
                continue
            if not STRICT_STORY_FILE_RE.match(linked_file.name):
                self.add_error(
                    str(self.story_index_path),
                    f"Story index includes non-strict story filename: {rel}",
                )

    def validate_blueprint(self) -> None:
        content = self.read_file(self.blueprint_path)
        if not content:
            return

        for lineno, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line.startswith("- ["):
                continue

            match = re.search(r"\[(F\d{4}(?:-S\d{4})?)[^\]]*\]\((features/[^)]+)\)\s*-\s*(.+)$", line)
            if not match:
                continue

            item_id = match.group(1)
            rel_path = match.group(2)
            status_text = match.group(3)
            target = self.root_dir / rel_path

            if not target.exists():
                self.add_error(
                    f"{self.blueprint_path}:{lineno}",
                    f"Blueprint link target missing for {item_id}: {rel_path}",
                )
                continue

            is_archived_status = "archived" in status_text.lower()
            points_to_archive = "/archive/" in rel_path

            if is_archived_status and not points_to_archive:
                self.add_error(
                    f"{self.blueprint_path}:{lineno}",
                    f"{item_id} marked archived but link is not archive path: {rel_path}",
                )

            feature_id = item_id.split("-")[0]
            if feature_id in self.registry_archived and not points_to_archive:
                self.add_error(
                    f"{self.blueprint_path}:{lineno}",
                    f"{item_id} belongs to archived feature {feature_id} but link is active path",
                )
            if feature_id in self.registry_active and points_to_archive:
                self.add_error(
                    f"{self.blueprint_path}:{lineno}",
                    f"{item_id} belongs to active feature {feature_id} but link points to archive",
                )

            if "-S" in item_id:
                file_prefix = "-".join(target.stem.split("-")[:2])
                if file_prefix != item_id:
                    self.add_error(
                        f"{self.blueprint_path}:{lineno}",
                        f"Blueprint story link ID mismatch: label {item_id}, file {target.name}",
                    )

    def validate(self) -> int:
        if not self.features_dir.exists():
            self.add_error(str(self.features_dir), "Features directory does not exist")
            self.print_report()
            return 1

        self.load_registry()
        self.load_roadmap()
        story_files, story_ids = self.collect_story_files()
        self.validate_story_index(story_files, story_ids)
        self.validate_blueprint()

        self.print_report()
        return 1 if any(issue.severity == "ERROR" for issue in self.issues) else 0

    def print_report(self) -> None:
        errors = [issue for issue in self.issues if issue.severity == "ERROR"]
        warnings = [issue for issue in self.issues if issue.severity == "WARNING"]

        if errors:
            print("\nERRORS:")
            for issue in errors:
                print(f"  - [{issue.location}] {issue.message}")

        if warnings:
            print("\nWARNINGS:")
            for issue in warnings:
                print(f"  - [{issue.location}] {issue.message}")

        print("\nSummary:")
        print(f"  errors: {len(errors)}")
        print(f"  warnings: {len(warnings)}")

        if not errors and not warnings:
            print("  result: PASS")
        elif not errors:
            print("  result: PASS (with warnings)")
        else:
            print("  result: FAIL")


def _invoke_feature_evidence_validator(
    product_root: Path,
    feature: str | None,
    run_id: str | None,
    *,
    all_feature_evidence: bool = False,
) -> int:
    """Call validate-feature-evidence.py at --stage G6.

    Per §22 integration rules, tracker validation calls feature-evidence
    validation only at the pre-closeout candidate stage. Final G8 / closeout
    validation is invoked by the closeout action *after* tracker results are
    appended to lifecycle-gates.log.
    """
    import subprocess

    if not feature and not all_feature_evidence:
        print(
            "\nFeature evidence validation: not requested "
            "(use --feature for scoped validation or --all-feature-evidence for a repo-wide audit)."
        )
        return 0

    script = Path(__file__).resolve().parent / "validate-feature-evidence.py"
    cmd = [
        sys.executable,
        str(script),
        "--product-root",
        str(product_root),
        "--stage",
        "G6",
    ]
    if feature:
        cmd.extend(["--feature", feature])
    if run_id:
        cmd.extend(["--run-id", run_id])
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate planning tracker consistency")
    add_product_root_arg(parser)
    parser.add_argument(
        "--features-dir",
        default=None,
        help="Path to planning feature directory (default: {NEBULA_PRODUCT_ROOT}/planning-mds/features)",
    )
    parser.add_argument(
        "--blueprint",
        default=None,
        help="Path to blueprint file (default: {NEBULA_PRODUCT_ROOT}/planning-mds/BLUEPRINT.md)",
    )
    parser.add_argument(
        "--feature",
        default=None,
        help="Feature ID (e.g. F0036) to pass through to validate-feature-evidence.py",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="In-progress run ID to validate with --feature at --stage G6",
    )
    parser.add_argument(
        "--skip-feature-evidence",
        action="store_true",
        help="Skip the post-tracker call into validate-feature-evidence.py (testing / staged rollout)",
    )
    parser.add_argument(
        "--all-feature-evidence",
        action="store_true",
        help="After tracker validation, run repo-wide validate-feature-evidence.py at --stage G6",
    )
    args = parser.parse_args()

    if args.run_id and not args.feature:
        parser.error("--run-id requires --feature; run IDs are feature-scoped")
    if args.all_feature_evidence and args.feature:
        parser.error("--all-feature-evidence cannot be combined with --feature")

    product_root = resolve_product_root(args.product_root)
    features_dir = Path(args.features_dir) if args.features_dir else product_root / "planning-mds" / "features"
    blueprint = Path(args.blueprint) if args.blueprint else product_root / "planning-mds" / "BLUEPRINT.md"

    validator = TrackerValidator(features_dir, blueprint)
    tracker_exit = validator.validate()

    if args.skip_feature_evidence:
        return tracker_exit
    if not args.feature and not args.all_feature_evidence:
        print(
            "\nFeature evidence validation: not requested "
            "(use --feature for scoped validation or --all-feature-evidence for a repo-wide audit)."
        )
        return tracker_exit

    # §22 integration: scoped or explicit repo-wide tracker validation can call
    # feature-evidence at --stage G6. Tracker exit code stays authoritative for
    # tracker concerns; feature-evidence exit is or'd in to surface evidence
    # issues without masking tracker failures.
    fe_exit = _invoke_feature_evidence_validator(
        product_root,
        args.feature,
        args.run_id,
        all_feature_evidence=args.all_feature_evidence,
    )
    if tracker_exit != 0:
        return tracker_exit
    return fe_exit


if __name__ == "__main__":
    sys.exit(main())
