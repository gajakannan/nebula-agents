#!/usr/bin/env python3
"""
Story Index Generator

Generates an index/table of contents for all user stories across feature folders.
Extracts story ID, title, priority, phase, and feature from each story file.

Stories are colocated in feature folders:
  {PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/F{NNNN}-S{NNNN}-{slug}.md

Usage:
    python generate-story-index.py [--product-root PATH] [features-directory]
    python generate-story-index.py
    python generate-story-index.py /path/to/features

If no features directory is supplied the script defaults to
{PRODUCT_ROOT}/planning-mds/features.

Output:
    Creates STORY-INDEX.md in the features directory
"""

import argparse
import sys
import io
import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402

# Windows cp1252 stdout can't encode emojis used in report output.
# Reconfigure to utf-8 unconditionally — safe on all platforms.
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Files in feature folders that are NOT stories — skip during scanning.
_SKIP_FILENAMES = frozenset({
    "PRD.MD", "README.MD", "STATUS.MD", "GETTING-STARTED.MD",
    "STORY-INDEX.MD", "REGISTRY.MD",
})


def _is_story_file(path: Path) -> bool:
    """Return True if *path* follows strict story naming (F*-S*-*.md)."""
    if path.name.upper() in _SKIP_FILENAMES:
        return False
    if re.match(r"F\d{4}-S\d{4}", path.name):
        return True
    return False


@dataclass
class StoryMetadata:
    """Metadata extracted from a story file."""
    file_path: Path
    story_id: Optional[str] = None
    title: Optional[str] = None
    feature: Optional[str] = None
    priority: Optional[str] = None
    phase: Optional[str] = None
    persona: Optional[str] = None

class StoryIndexGenerator:
    def __init__(self, features_dir: str):
        self.features_dir = Path(features_dir)
        self.stories: List[StoryMetadata] = []

    def extract_metadata(self, file_path: Path) -> StoryMetadata:
        """Extract metadata from a story markdown file."""
        metadata = StoryMetadata(file_path=file_path)

        try:
            content = file_path.read_text(encoding='utf-8')

            # Extract Story ID
            story_id_match = re.search(r"\*\*Story ID:\*\*\s*([^\n]+)", content)
            if story_id_match:
                metadata.story_id = story_id_match.group(1).strip()
            else:
                # Try to extract from strict filename (e.g., F0001-S0001-example.md)
                filename_match = re.match(r"(F\d{4}-S\d{4})", file_path.stem)
                if filename_match:
                    metadata.story_id = filename_match.group(1)

            # Extract Title
            title_match = re.search(r"\*\*Title:\*\*\s*([^\n]+)", content)
            if title_match:
                metadata.title = title_match.group(1).strip()
            else:
                # Try to extract from first heading
                heading_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                if heading_match:
                    metadata.title = heading_match.group(1).strip()

            # Extract Feature
            feature_match = re.search(r"\*\*Feature:\*\*\s*([^\n]+)", content)
            if feature_match:
                metadata.feature = feature_match.group(1).strip()
            else:
                # Infer feature from parent directory name (e.g., F0001-dashboard)
                parent_name = file_path.parent.name
                if re.match(r"F\d{4}-", parent_name):
                    metadata.feature = parent_name

            # Extract Priority
            priority_match = re.search(r"\*\*Priority:\*\*\s*([^\n]+)", content)
            if priority_match:
                metadata.priority = priority_match.group(1).strip()

            # Extract Phase
            phase_match = re.search(r"\*\*Phase:\*\*\s*([^\n]+)", content)
            if phase_match:
                metadata.phase = phase_match.group(1).strip()

            # Extract Persona from "As a..."
            persona_match = re.search(r"\*\*As\s+a\*\*\s+([^\n*]+)", content)
            if persona_match:
                metadata.persona = persona_match.group(1).strip()

        except Exception as e:
            print(f"Warning: Failed to extract metadata from {file_path.name}: {e}")

        return metadata

    def scan_stories(self):
        """Scan feature directories for story markdown files."""
        if not self.features_dir.exists():
            print(f"Error: Directory not found: {self.features_dir}")
            sys.exit(1)

        # Find story files across all feature folders
        story_files = [
            f for f in sorted(self.features_dir.rglob("*.md"))
            if _is_story_file(f)
        ]

        if not story_files:
            print(f"Warning: No story files found in {self.features_dir}")

        # Extract metadata from each file
        for file_path in story_files:
            metadata = self.extract_metadata(file_path)
            self.stories.append(metadata)

        print(f"Found {len(self.stories)} story files")

    def generate_index(self) -> str:
        """Generate markdown index content."""
        lines = []

        # Header
        lines.append("# User Story Index")
        lines.append("")
        lines.append("Auto-generated index of all user stories across feature folders.")
        lines.append("")
        lines.append(f"**Total Stories:** {len(self.stories)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Group by Feature
        features: Dict[str, List[StoryMetadata]] = {}
        no_feature: List[StoryMetadata] = []

        for story in self.stories:
            if story.feature:
                if story.feature not in features:
                    features[story.feature] = []
                features[story.feature].append(story)
            else:
                no_feature.append(story)

        # Generate table for each feature
        for feature_name in sorted(features.keys()):
            stories = features[feature_name]

            lines.append(f"## {feature_name}")
            lines.append("")
            lines.append("| Story ID | Title | Priority | Phase | Persona |")
            lines.append("|----------|-------|----------|-------|---------|")

            for story in sorted(stories, key=lambda s: s.story_id or ""):
                story_id = story.story_id or "?"
                title = story.title or "Untitled"
                priority = story.priority or "-"
                phase = story.phase or "-"
                persona = story.persona or "-"

                # Create link to story file with relative path
                rel_path = story.file_path.relative_to(self.features_dir)
                file_link = f"[{story_id}](./{rel_path})"

                lines.append(f"| {file_link} | {title} | {priority} | {phase} | {persona} |")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Stories without feature
        if no_feature:
            lines.append("## Uncategorized Stories")
            lines.append("")
            lines.append("| Story ID | Title | Priority | Phase | Persona |")
            lines.append("|----------|-------|----------|-------|---------|")

            for story in sorted(no_feature, key=lambda s: s.story_id or ""):
                story_id = story.story_id or "?"
                title = story.title or "Untitled"
                priority = story.priority or "-"
                phase = story.phase or "-"
                persona = story.persona or "-"

                # Create link with relative path
                rel_path = story.file_path.relative_to(self.features_dir)
                file_link = f"[{story_id}](./{rel_path})"

                lines.append(f"| {file_link} | {title} | {priority} | {phase} | {persona} |")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Summary by Phase
        lines.append("## Summary by Phase")
        lines.append("")

        phase_counts: Dict[str, int] = {}
        for story in self.stories:
            phase = story.phase or "Unspecified"
            phase_counts[phase] = phase_counts.get(phase, 0) + 1

        lines.append("| Phase | Count |")
        lines.append("|-------|-------|")
        for phase in sorted(phase_counts.keys()):
            lines.append(f"| {phase} | {phase_counts[phase]} |")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Summary by Priority
        lines.append("## Summary by Priority")
        lines.append("")

        priority_counts: Dict[str, int] = {}
        for story in self.stories:
            priority = story.priority or "Unspecified"
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        lines.append("| Priority | Count |")
        lines.append("|----------|-------|")
        for priority in ["Critical", "High", "Medium", "Low", "Unspecified"]:
            if priority in priority_counts:
                lines.append(f"| {priority} | {priority_counts[priority]} |")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*Generated by generate-story-index.py*")

        return "\n".join(lines)

    def write_index(self, output_path: Optional[Path] = None):
        """Write index to file."""
        if output_path is None:
            output_path = self.features_dir / "STORY-INDEX.md"

        index_content = self.generate_index()

        try:
            output_path.write_text(index_content, encoding='utf-8')
            print(f"✅ Story index generated: {output_path}")
        except Exception as e:
            print(f"❌ Failed to write index: {e}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Generate STORY-INDEX.md for planning features")
    add_product_root_arg(parser)
    parser.add_argument(
        "features_dir",
        nargs="?",
        default=None,
        help="Path to planning features directory (default: {PRODUCT_ROOT}/planning-mds/features)",
    )
    args = parser.parse_args()

    if args.features_dir:
        features_dir = args.features_dir
    else:
        product_root = resolve_product_root(args.product_root)
        features_dir = str(product_root / "planning-mds" / "features")

    print(f"Generating story index for: {features_dir}")
    print("-" * 60)

    generator = StoryIndexGenerator(features_dir)
    generator.scan_stories()
    generator.write_index()

if __name__ == "__main__":
    main()
