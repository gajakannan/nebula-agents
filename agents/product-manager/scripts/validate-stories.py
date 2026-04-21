#!/usr/bin/env python3
"""
Story Validation Script

Validates user stories for completeness and quality.
Checks that stories follow the template and have all required sections.

Stories are colocated in feature folders: {PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/F{NNNN}-S{NNNN}-{slug}.md

Usage:
    python3 validate-stories.py <file-or-dir> [<file-or-dir> ...]
    python3 validate-stories.py {PRODUCT_ROOT}/planning-mds/features/
    python3 validate-stories.py {PRODUCT_ROOT}/planning-mds/features/F0001-dashboard/F0001-S0001-nudge-cards.md
    python3 validate-stories.py --strict-warnings {PRODUCT_ROOT}/planning-mds/features/
"""

import sys
import io
import re
import argparse
from pathlib import Path

# Windows cp1252 stdout can't encode emojis used in report output.
# Reconfigure to utf-8 unconditionally — safe on all platforms.
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from typing import List, Tuple, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402


STRICT_WARNING_PREFIXES = (
    "Acceptance criteria contain vague terms:",
    "No edge cases or error scenarios documented",
    "No permission/authorization checks documented",
    "Story involves data mutation but has no audit/timeline requirements",
)

class StoryValidator:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.content = ""
        self.errors = []
        self.warnings = []

    def load_story(self) -> bool:
        """Load story file content."""
        try:
            self.content = self.file_path.read_text(encoding='utf-8')
            return True
        except Exception as e:
            self.errors.append(f"Failed to read file: {e}")
            return False

    def validate(self, strict_warnings: bool = False) -> Tuple[bool, List[str], List[str]]:
        """
        Validate story completeness and quality.
        Returns (is_valid, errors, warnings)
        """
        if not self.load_story():
            return False, self.errors, self.warnings

        # Required sections
        self.check_single_story_per_file()
        self.check_story_header_fields()
        self.check_user_story_format()
        self.check_context_background()
        self.check_acceptance_criteria()
        self.check_data_requirements()
        self.check_role_based_visibility()
        self.check_non_functional_expectations()
        self.check_dependencies()
        self.check_out_of_scope()
        self.check_questions_assumptions()
        self.check_definition_of_done()

        # Quality checks
        self.check_invest_criteria()
        self.check_acceptance_criteria_quality()

        if strict_warnings:
            self.promote_key_warnings_to_errors()

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def promote_key_warnings_to_errors(self):
        """
        Promote high-impact quality warnings to errors in strict mode.
        This keeps default behavior lenient while allowing stricter CI/pipeline usage.
        """
        retained_warnings = []
        for warning in self.warnings:
            if any(warning.startswith(prefix) for prefix in STRICT_WARNING_PREFIXES):
                self.errors.append(f"[strict-warning] {warning}")
            else:
                retained_warnings.append(warning)
        self.warnings = retained_warnings

    def check_user_story_format(self):
        """Check for 'As a...I want...So that...' format."""
        story_pattern = r"\*\*As\s+a\*\*.*\*\*I\s+want\*\*.*\*\*So\s+that\*\*"

        if not re.search(story_pattern, self.content, re.IGNORECASE | re.DOTALL):
            self.errors.append("Missing or malformed user story (As a...I want...So that...)")
        else:
            # Check if persona is specific (not just "user")
            if re.search(r"\*\*As\s+a\*\*\s+(user|someone|person)", self.content, re.IGNORECASE):
                self.warnings.append("User story uses generic persona 'user' - be more specific")

    def check_single_story_per_file(self):
        """Ensure story files contain exactly one story."""
        story_id_markers = re.findall(r"\*\*Story ID:\*\*", self.content)
        if len(story_id_markers) > 1:
            self.errors.append("Multiple stories detected in one file. Keep one story per file.")

        # Combined documents may use headings like "## Story X: ..."
        legacy_story_headings = re.findall(r"^##\s+Story\s+[A-Za-z0-9_-]+", self.content, re.IGNORECASE | re.MULTILINE)
        if len(legacy_story_headings) > 1:
            self.errors.append("Multiple story sections detected. Split into separate files (one story per file).")

    def check_acceptance_criteria(self):
        """Check for acceptance criteria section."""
        section = self.get_section_content("Acceptance Criteria")
        if not section:
            self.errors.append("Missing 'Acceptance Criteria' section")
            return

        # Check for at least one Given/When/Then or checklist item
        has_given_when_then = bool(re.search(r"(Given|When|Then)", section))
        has_checklist = bool(re.search(r"- \[ \]", section))

        if not has_given_when_then and not has_checklist:
            self.errors.append("Acceptance criteria section exists but has no criteria (use Given/When/Then or checklist)")

    def check_data_requirements(self):
        """Check for data requirements section."""
        if not self.get_section_content("Data Requirements"):
            self.errors.append("Missing 'Data Requirements' section")

    def check_role_based_visibility(self):
        """Check for role-based visibility section."""
        if not self.get_section_content("Role-Based Visibility"):
            self.errors.append("Missing 'Role-Based Visibility' section")

    def check_non_functional_expectations(self):
        """Check for non-functional expectations section."""
        if not self.get_section_content("Non-Functional Expectations"):
            self.warnings.append("Missing 'Non-Functional Expectations' section (add if applicable)")

    def check_dependencies(self):
        """Check for dependencies section."""
        if not self.get_section_content("Dependencies"):
            self.errors.append("Missing 'Dependencies' section")

    def check_out_of_scope(self):
        """Check for out of scope section."""
        if not self.get_section_content("Out of Scope"):
            self.errors.append("Missing 'Out of Scope' section")

    def check_questions_assumptions(self):
        """Check for questions & assumptions section."""
        if not self.get_section_content("Questions & Assumptions"):
            self.warnings.append("Missing 'Questions & Assumptions' section")

    def check_definition_of_done(self):
        """Check for definition of done."""
        if not self.get_section_content("Definition of Done"):
            self.errors.append("Missing 'Definition of Done' section")

    def check_story_header_fields(self):
        """Check for story header fields in the template."""
        required_fields = [
            "Story ID",
            "Title",
            "Priority",
            "Phase",
        ]
        for field in required_fields:
            if not re.search(rf"\*\*{re.escape(field)}:\*\*", self.content):
                self.errors.append(f"Missing story header field: {field}")

        if not re.search(r"\*\*Feature:\*\*", self.content):
            self.errors.append("Missing story header field: Feature")

    def check_context_background(self):
        """Check for context & background section."""
        if not self.get_section_content("Context & Background"):
            self.warnings.append("Missing 'Context & Background' section")

    def check_invest_criteria(self):
        """Check INVEST criteria quality."""

        user_story_section = self.get_section_content("User Story")
        invest_scope = user_story_section if user_story_section else self.content

        # Independent: Check for phrases indicating dependencies
        dependency_phrases = ["depends on", "requires", "needs", "after", "once", "when.*is complete"]
        for phrase in dependency_phrases:
            if re.search(phrase, invest_scope, re.IGNORECASE):
                self.warnings.append(f"Story may have dependencies - check 'Independent' (INVEST)")
                break

        # Valuable: Check for technical-only language
        technical_terms = ["database", "api", "endpoint", "schema", "migration", "refactor"]
        story_section = re.search(r"\*\*As\s+a\*\*.*?\*\*So\s+that\*\*.*?(?=\n\n|\Z)", self.content, re.DOTALL | re.IGNORECASE)
        if story_section:
            story_text = story_section.group(0).lower()
            if any(term in story_text for term in technical_terms):
                self.warnings.append("Story may be technical-focused rather than user-value focused (INVEST - Valuable)")

        # Small: Check story length (rough heuristic)
        if len(self.content) > 10000:
            self.warnings.append("Story is very large (>10k chars) - consider breaking into smaller slices (INVEST - Small)")

        # Testable: Check for vague terms in acceptance criteria
        vague_terms = ["properly", "correctly", "appropriate", "fast", "user-friendly", "intuitive"]
        ac_section = self.get_section_content("Acceptance Criteria")
        if ac_section:
            ac_text = ac_section.lower()
            found_vague = [term for term in vague_terms if term in ac_text]
            if found_vague:
                self.warnings.append(f"Acceptance criteria contain vague terms: {', '.join(found_vague)} - be more specific (INVEST - Testable)")

    def check_acceptance_criteria_quality(self):
        """Check acceptance criteria quality."""
        ac_section = self.get_section_content("Acceptance Criteria")
        if not ac_section:
            return
        ac_text = ac_section.lower()

        # Check for edge cases / negative-path outcomes (heuristic).
        error_signal_patterns = [
            r"\bedge cases?\b",
            r"\berror scenarios?\b",
            r"\bhttp\s*(4\d{2}|5\d{2})\b",
            r"\bstatus\s*code\s*(4\d{2}|5\d{2})\b",
            r"\b(forbidden|unauthorized|not found|conflict|bad request|denied|rejected)\b",
        ]
        if not self.contains_pattern(ac_section, error_signal_patterns):
            self.warnings.append("No edge cases or error scenarios documented - consider adding")

        # Check for permission/authorization semantics across key sections.
        auth_scope = "\n".join(
            [
                ac_section,
                self.get_section_content("Role-Based Visibility"),
                self.get_section_content("Non-Functional Expectations"),
            ]
        )
        auth_signal_patterns = [
            r"\bpermissions?\b",
            r"\bauthoriz(?:e|ed|ation|ing)\b",
            r"\bauthenticat(?:e|ed|ion|ing)\b",
            r"\bauthz\b",
            r"\brbac\b",
            r"\babac\b",
            r"\bforbidden\b",
            r"\bunauthorized\b",
            r"\bhttp\s*(401|403)\b",
        ]
        if not self.contains_pattern(auth_scope, auth_signal_patterns):
            self.warnings.append("No permission/authorization checks documented - consider adding if applicable")

        # Check for audit trail (if mutation involved)
        mutation_keywords = ["create", "update", "delete", "change", "transition", "modify"]
        mutation_scope = "\n".join(
            [
                self.get_section_content("User Story"),
                ac_section,
            ]
        ).lower()
        if any(keyword in mutation_scope for keyword in mutation_keywords):
            if "timeline" not in ac_text and "audit" not in ac_text:
                self.warnings.append("Story involves data mutation but has no audit/timeline requirements")

    @staticmethod
    def contains_pattern(text: str, patterns: List[str]) -> bool:
        """Return True when any regex pattern matches text (case-insensitive)."""
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

    def get_section_content(self, section_name: str) -> str:
        """Return the content of a markdown section by name (## or ###)."""
        pattern = re.compile(rf"^##+\s+{re.escape(section_name)}\s*$", re.IGNORECASE | re.MULTILINE)
        match = pattern.search(self.content)
        if not match:
            return ""
        start = match.end()
        next_heading = re.search(r"^##+\s+", self.content[start:], re.MULTILINE)
        end = start + next_heading.start() if next_heading else len(self.content)
        return self.content[start:end].strip()

# Files in feature folders that are NOT stories — skip during validation.
_SKIP_FILENAMES = frozenset({
    "PRD.MD", "README.MD", "STATUS.MD", "GETTING-STARTED.MD",
    "STORY-INDEX.MD", "REGISTRY.MD",
})


def _is_story_file(path: Path) -> bool:
    """Return True if *path* follows the strict story naming pattern
    F{NNNN}-S{NNNN}-*.md and is not a feature-level document."""
    if path.name.upper() in _SKIP_FILENAMES:
        return False
    # When scanning a directory, only pick up files matching the story pattern
    if re.match(r"F\d{4}-S\d{4}", path.name):
        return True
    return False


def collect_story_files(paths: Iterable[str]) -> Tuple[List[Path], List[str]]:
    story_files: List[Path] = []
    errors: List[str] = []

    for raw in paths:
        path = Path(raw)
        if not path.exists():
            errors.append(f"Path not found: {path}")
            continue
        if path.is_dir():
            # Scan feature folders for story files (F*-S*.md)
            for item in sorted(path.rglob("*.md")):
                if _is_story_file(item):
                    story_files.append(item)
        else:
            if _is_story_file(path):
                story_files.append(path)
            else:
                errors.append(
                    f"File does not match strict story naming pattern F{{NNNN}}-S{{NNNN}}-*.md: {path}"
                )

    # Deduplicate while preserving order
    seen = set()
    unique_files = []
    for item in story_files:
        if item not in seen:
            seen.add(item)
            unique_files.append(item)

    return unique_files, errors


def main():
    parser = argparse.ArgumentParser(description="Validate user story files for completeness and quality")
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Promote key quality warnings (testability/security/audit gaps) to errors",
    )
    add_product_root_arg(parser)
    parser.add_argument(
        "paths",
        nargs="*",
        help=(
            "Story files or directories to validate. "
            "Defaults to {PRODUCT_ROOT}/planning-mds/features."
        ),
    )
    args = parser.parse_args()

    product_root = resolve_product_root(args.product_root)
    paths = args.paths if args.paths else [str(product_root / "planning-mds" / "features")]

    story_files, path_errors = collect_story_files(paths)

    if path_errors:
        for error in path_errors:
            print(f"❌ {error}")
        sys.exit(1)

    if not story_files:
        print("ℹ️  No story files found to validate (expected pattern: F{NNNN}-S{NNNN}-*.md).")
        sys.exit(0)

    total_errors = 0
    total_warnings = 0

    if args.strict_warnings:
        print("Strict warning mode enabled: key warnings will fail validation.\n")

    for file_path in story_files:
        print(f"Validating story: {file_path}")
        print("-" * 60)

        validator = StoryValidator(str(file_path))
        is_valid, errors, warnings = validator.validate(strict_warnings=args.strict_warnings)

        if errors:
            print("\n❌ ERRORS (Must Fix):")
            for i, error in enumerate(errors, 1):
                print(f"  {i}. {error}")

        if warnings:
            print("\n⚠️  WARNINGS (Should Fix):")
            for i, warning in enumerate(warnings, 1):
                print(f"  {i}. {warning}")

        print("\n" + "=" * 60)
        if is_valid and not warnings:
            print("✅ Story validation PASSED - No issues found!")
        elif is_valid:
            print(f"⚠️  Story validation PASSED with {len(warnings)} warning(s)")
        else:
            print(f"❌ Story validation FAILED with {len(errors)} error(s) and {len(warnings)} warning(s)")

        total_errors += len(errors)
        total_warnings += len(warnings)

    if total_errors > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
