#!/usr/bin/env python3
"""
Architecture Validation Script

Validates architecture specifications in BLUEPRINT.md for completeness.
Pulls the entity list from the domain glossary.

Usage:
    python3 validate-architecture.py [--product-root PATH] [blueprint-path] [glossary-path]
    python3 validate-architecture.py
    python3 validate-architecture.py --product-root ../my-product
    python3 validate-architecture.py /path/to/BLUEPRINT.md /path/to/glossary.md

Defaults resolve to {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md and
{PRODUCT_ROOT}/planning-mds/domain/glossary.md.
"""

import argparse
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402

class ArchitectureValidator:
    def __init__(self, file_path: str, glossary_path: str):
        self.file_path = Path(file_path)
        self.glossary_path = Path(glossary_path)
        self.content = ""
        self.errors = []
        self.warnings = []
        self.entities = []
        self.workflows = []

    def load_blueprint(self) -> bool:
        """Load BLUEPRINT.md content."""
        try:
            self.content = self.file_path.read_text(encoding='utf-8')
            return True
        except Exception as e:
            self.errors.append(f"Failed to read file: {e}")
            return False

    def extract_entities_from_glossary(self) -> List[str]:
        """
        Extract entity names from the domain glossary.

        Looks for entries marked with **Type:** Entity and extracts
        the ### heading, converting to PascalCase (removing spaces).
        Parenthetical content in headings is stripped first.

        Example glossary entry:
        ### Activity Timeline Event
        **Type:** Entity
        **Definition:** ...

        Yields: ActivityTimelineEvent
        """
        try:
            glossary_content = self.glossary_path.read_text(encoding='utf-8')
        except Exception as e:
            self.warnings.append(f"Could not read glossary at '{self.glossary_path}': {e}")
            return []

        entities = []
        current_heading = None

        for line in glossary_content.split('\n'):
            # Track ### headings
            heading_match = re.match(r'^###\s+(.+)$', line.strip())
            if heading_match:
                current_heading = heading_match.group(1).strip()
                continue

            # Check for **Type:** Entity marker under the current heading
            if current_heading and re.match(r'^\*\*Type:\*\*\s*Entity', line.strip()):
                # Strip parenthetical content (e.g., "CEO (Chief Executive Officer)" -> "CEO")
                clean = re.sub(r'\s*\(.*?\)', '', current_heading).strip()
                words = clean.split()
                # Single word: preserve as-is (handles acronyms like CEO, already-PascalCase like UserProfile)
                # Multi-word: join into PascalCase (e.g., "Activity Timeline Event" -> ActivityTimelineEvent)
                pascal_name = words[0] if len(words) == 1 else ''.join(w.capitalize() for w in words)
                entities.append(pascal_name)
                current_heading = None  # Reset; don't match the same heading again

        return entities

    def extract_workflows_from_blueprint(self) -> List[str]:
        """
        Extract workflow names from section 1.4 of BLUEPRINT.md.

        Expected format:
        ### 1.4 Critical workflows (baseline)
        WorkflowName: State1 → State2 → ...
        AnotherWorkflow: State1 → State2 → ...
        """
        section = self.get_section_content("1.4")
        workflows = []

        for line in section.split('\n'):
            line = line.strip()
            # Match lines like "WorkflowName: State1 → State2 → ..."
            match = re.match(r'^([A-Z][A-Za-z]+):\s+', line)
            if match:
                workflow = match.group(1)
                workflows.append(workflow)

        return workflows

    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """Validate architecture completeness."""
        if not self.load_blueprint():
            return False, self.errors, self.warnings

        # Extract entities from glossary, workflows from BLUEPRINT.md section 1.4
        self.entities = self.extract_entities_from_glossary()
        self.workflows = self.extract_workflows_from_blueprint()

        # Check Phase B sections (4.x)
        self.check_service_boundaries()
        self.check_data_model()
        self.check_workflow_rules()
        self.check_authorization_model()
        self.check_api_contracts()
        self.check_nfrs()

        # Quality checks
        self.check_for_todos()
        self.check_consistency()

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def check_service_boundaries(self):
        """Check for service boundaries section (4.1)."""
        if "## 4.1" not in self.content and "### 4.1" not in self.content:
            self.errors.append("Missing Section 4.1: Service Boundaries")
        elif "TODO" in self.get_section_content("4.1"):
            self.errors.append("Section 4.1 (Service Boundaries) contains TODOs")

    def check_data_model(self):
        """Check for data model section (4.2)."""
        if "## 4.2" not in self.content and "### 4.2" not in self.content:
            self.errors.append("Missing Section 4.2: Data Model")
            return

        section = self.get_section_content("4.2")

        if "TODO" in section:
            self.errors.append("Section 4.2 (Data Model) contains TODOs")

        # Check for key entity definitions (extracted from section 1.3)
        # Only check first few entities to avoid too many warnings
        key_entities = self.entities[:5] if len(self.entities) > 5 else self.entities
        for entity in key_entities:
            if entity not in section:
                self.warnings.append(f"Data Model doesn't mention '{entity}' entity (from glossary)")

        # Check for audit fields mention
        if "CreatedAt" not in section and "created_at" not in section.lower():
            self.warnings.append("Data Model doesn't mention audit fields (CreatedAt, UpdatedAt)")

    def check_workflow_rules(self):
        """Check for workflow rules section (4.3)."""
        if "## 4.3" not in self.content and "### 4.3" not in self.content:
            self.errors.append("Missing Section 4.3: Workflow Rules")
            return

        section = self.get_section_content("4.3")

        if "TODO" in section:
            self.errors.append("Section 4.3 (Workflow Rules) contains TODOs")

        # Check for workflow definitions (extracted from section 1.4)
        for workflow in self.workflows:
            if workflow not in section:
                self.warnings.append(f"Workflow Rules don't mention '{workflow}' workflow (from section 1.4)")

        # Check for transition mention
        if "transition" not in section.lower():
            self.warnings.append("Workflow Rules don't mention state transitions")

    def check_authorization_model(self):
        """Check for authorization model section (4.4)."""
        if "## 4.4" not in self.content and "### 4.4" not in self.content:
            self.errors.append("Missing Section 4.4: Authorization Model")
            return

        section = self.get_section_content("4.4")

        if "TODO" in section:
            self.errors.append("Section 4.4 (Authorization Model) contains TODOs")

        # Check for ABAC components
        if "subject" not in section.lower() and "user" not in section.lower():
            self.warnings.append("Authorization Model doesn't define subject attributes")

        if "resource" not in section.lower():
            self.warnings.append("Authorization Model doesn't define resource attributes")

        if "action" not in section.lower() and "permission" not in section.lower():
            self.warnings.append("Authorization Model doesn't define actions/permissions")

    def check_api_contracts(self):
        """Check for API contracts section (4.5)."""
        if "## 4.5" not in self.content and "### 4.5" not in self.content:
            self.errors.append("Missing Section 4.5: API Contracts")
            return

        section = self.get_section_content("4.5")

        if "TODO" in section:
            self.errors.append("Section 4.5 (API Contracts) contains TODOs")

        # Check for CRUD operations
        if "POST" not in section and "CREATE" not in section.upper():
            self.warnings.append("API Contracts don't mention POST/CREATE operations")

        if "GET" not in section and "READ" not in section.upper():
            self.warnings.append("API Contracts don't mention GET/READ operations")

    def check_nfrs(self):
        """Check for NFRs section (4.6)."""
        if "## 4.6" not in self.content and "### 4.6" not in self.content:
            self.errors.append("Missing Section 4.6: Non-Functional Requirements")
            return

        section = self.get_section_content("4.6")

        if "TODO" in section:
            self.errors.append("Section 4.6 (NFRs) contains TODOs")

        # Check for key NFR categories
        nfr_categories = ["performance", "security", "availability", "scalability"]
        for category in nfr_categories:
            if category not in section.lower():
                self.warnings.append(f"NFRs don't mention '{category}'")

        # Check for specific metrics
        if "ms" not in section and "second" not in section.lower():
            self.warnings.append("NFRs don't specify performance metrics (e.g., < 500ms)")

    def check_for_todos(self):
        """Check for remaining TODOs in Phase B."""
        phase_b_section = self.get_section_content("4")
        todo_count = phase_b_section.count("TODO")

        if todo_count > 0:
            self.errors.append(f"Phase B contains {todo_count} TODO(s) - all must be resolved")

    def check_consistency(self):
        """Check for consistency across sections."""
        # Check if entities in data model match API contracts
        data_model = self.get_section_content("4.2")
        api_contracts = self.get_section_content("4.5")

        # Simple heuristic: check if major entities appear in both
        # Check first few entities to avoid too many warnings
        entities_to_check = self.entities[:5] if len(self.entities) > 5 else self.entities
        for entity in entities_to_check:
            if entity in data_model and entity not in api_contracts:
                self.warnings.append(f"Entity '{entity}' in Data Model but not in API Contracts")

    def get_section_content(self, section_num: str) -> str:
        """Extract content for a specific section (## or ###)."""
        start_pattern = re.compile(
            rf"^##+\s*{re.escape(section_num)}[.:\s].*$",
            re.IGNORECASE | re.MULTILINE,
        )
        match = start_pattern.search(self.content)
        if not match:
            return ""

        start = match.start()
        next_heading = re.search(r"^##+\s*\d", self.content[match.end():], re.MULTILINE)
        end = match.end() + next_heading.start() if next_heading else len(self.content)
        return self.content[start:end]

def main():
    parser = argparse.ArgumentParser(description="Validate architecture specification")
    add_product_root_arg(parser)
    parser.add_argument(
        "blueprint",
        nargs="?",
        default=None,
        help="Path to BLUEPRINT.md (default: {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md)",
    )
    parser.add_argument(
        "glossary",
        nargs="?",
        default=None,
        help="Path to glossary.md (default: {PRODUCT_ROOT}/planning-mds/domain/glossary.md)",
    )
    args = parser.parse_args()

    product_root = resolve_product_root(args.product_root)
    file_path = args.blueprint if args.blueprint else str(product_root / "planning-mds" / "BLUEPRINT.md")
    default_glossary = product_root / "planning-mds" / "domain" / "glossary.md"
    glossary_path = args.glossary if args.glossary else str(default_glossary)
    if glossary_path == str(default_glossary) and not default_glossary.exists():
        domain_dir = default_glossary.parent
        candidates = sorted(path for path in domain_dir.glob("*glossary*.md") if path.is_file())
        if len(candidates) == 1:
            glossary_path = str(candidates[0])
            print(f"Default glossary not found, using discovered glossary: {glossary_path}")

    print(f"Validating architecture specification: {file_path}")
    print(f"Using glossary: {glossary_path}")
    print("-" * 60)

    validator = ArchitectureValidator(file_path, glossary_path)
    is_valid, errors, warnings = validator.validate()

    # Print extracted context
    if validator.entities:
        print(f"\n[Entities] Extracted from glossary: {', '.join(validator.entities[:5])}")
        if len(validator.entities) > 5:
            print(f"           (and {len(validator.entities) - 5} more...)")
    if validator.workflows:
        print(f"[Workflows] Extracted from section 1.4: {', '.join(validator.workflows)}")

    # Print errors
    if errors:
        print("\n[ERROR] Must Fix:")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")

    # Print warnings
    if warnings:
        print("\n[WARNING] Should Fix:")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")

    # Print summary
    print("\n" + "=" * 60)
    if is_valid and not warnings:
        print("[PASS] Architecture validation PASSED - No issues found!")
        sys.exit(0)
    elif is_valid:
        print(f"[PASS] Architecture validation PASSED with {len(warnings)} warning(s)")
        sys.exit(0)
    else:
        print(f"[FAIL] Architecture validation FAILED with {len(errors)} error(s) and {len(warnings)} warning(s)")
        sys.exit(1)

if __name__ == "__main__":
    main()
