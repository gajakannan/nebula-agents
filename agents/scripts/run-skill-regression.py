#!/usr/bin/env python3
"""
Skill regression harness.

Validates:
1) Skill metadata completeness and format.
2) Skill structure quality (required sections + line count ceiling).
3) Trigger routing accuracy against a golden prompt set.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


REQUIRED_TOP_LEVEL_FIELDS = [
    "name",
    "description",
    "compatibility",
]

REQUIRED_FLEX_FIELDS = [
    "allowed-tools",
    "version",
    "author",
    "tags",
    "last_updated",
]

REQUIRED_H2_HEADINGS = [
    "Scope & Boundaries",
    "Degrees of Freedom",
    "Definition of Done",
    "Troubleshooting",
]

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "from",
    "into",
    "when",
    "does",
    "not",
    "use",
    "using",
    "write",
    "build",
    "create",
    "run",
    "set",
    "up",
    "all",
    "your",
    "you",
    "are",
    "how",
    "what",
    "our",
    "their",
    "will",
    "can",
    "new",
    "tier",
    "tiers",
}

SKILL_HINTS: Dict[str, List[str]] = {
    "product-manager": ["mvp", "persona", "personas", "story", "stories", "requirements", "acceptance", "scope"],
    "architect": ["architecture", "data", "model", "api", "contract", "adr", "design"],
    "backend-developer": ["backend", "endpoint", "api", "migration", "entity", "repository", "dotnet"],
    "frontend-developer": ["frontend", "react", "screen", "form", "component", "ui", "typescript"],
    "ai-engineer": ["llm", "prompt", "mcp", "agent", "workflow", "model", "inference"],
    "quality-engineer": ["test", "tests", "coverage", "e2e", "performance", "regression"],
    "devops": ["docker", "compose", "deploy", "deployment", "infrastructure", "pipeline", "cicd", "monitoring"],
    "code-reviewer": ["review", "pull", "request", "code", "quality", "maintainability", "pr"],
    "security": ["security", "owasp", "threat", "vulnerability", "auth", "audit"],
    "technical-writer": ["documentation", "docs", "runbook", "guide", "api"],
    "blogger": ["blog", "devlog", "retrospective", "lessons", "article"],
}


@dataclass
class Skill:
    folder: str
    path: Path
    metadata: Dict
    body: str
    line_count: int
    profile_tokens: set


def resolve_field(frontmatter: Dict, field: str):
    """
    Resolve a skill field from frontmatter.

    Supports both:
    - top-level field (legacy/current variants)
    - nested field under `metadata` (canonical current format)
    """
    if field in frontmatter:
        return frontmatter[field]
    nested = frontmatter.get("metadata")
    if isinstance(nested, dict) and field in nested:
        return nested[field]
    return None


def tokenize(text: str) -> set:
    tokens = set()
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if len(token) < 2 or token in STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def parse_frontmatter(path: Path) -> Tuple[Dict, str]:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Missing YAML frontmatter start delimiter")

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("Missing YAML frontmatter end delimiter")

    frontmatter = "\n".join(lines[1:end_idx])
    metadata = yaml.safe_load(frontmatter)
    if not isinstance(metadata, dict):
        raise ValueError("Frontmatter must parse to a mapping")

    body = "\n".join(lines[end_idx + 1 :])
    return metadata, body


def build_skill(path: Path) -> Skill:
    metadata, body = parse_frontmatter(path)
    folder = path.parent.name
    tags = resolve_field(metadata, "tags")
    profile = " ".join(
        [
            str(metadata.get("description", "")),
            str(metadata.get("name", "")),
            " ".join(tags if isinstance(tags, list) else []),
            folder.replace("-", " "),
        ]
    )
    return Skill(
        folder=folder,
        path=path,
        metadata=metadata,
        body=body,
        line_count=len(path.read_text(encoding="utf-8").splitlines()),
        profile_tokens=tokenize(profile),
    )


def extract_h2_headings(body: str) -> set:
    headings = set()
    for line in body.splitlines():
        match = re.match(r"^\s{0,3}##\s+(.+?)\s*#*\s*$", line)
        if match:
            headings.add(match.group(1).strip())
    return headings


def has_feedback_loop_section(body: str) -> bool:
    for line in body.splitlines():
        stripped = line.strip()
        if re.match(r"^#{2,6}\s+.*\bfeedback loop\b.*$", stripped, re.IGNORECASE):
            return True
        if re.match(r"^\*\*[^*]*\bfeedback loop\b[^*]*\*\*\s*:?\s*$", stripped, re.IGNORECASE):
            return True
    return False


def validate_metadata(skill: Skill, errors: List[str]) -> None:
    md = skill.metadata
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if not md.get(field):
            errors.append(f"{skill.path}: missing top-level frontmatter field '{field}'")

    for field in REQUIRED_FLEX_FIELDS:
        if resolve_field(md, field) is None:
            errors.append(
                f"{skill.path}: missing skill field '{field}' "
                "(expected top-level or metadata.<field>)"
            )

    version_raw = resolve_field(md, "version")
    version = str(version_raw or "")
    if version and not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append(f"{skill.path}: version must be semver (x.y.z), got '{version}'")

    tags = resolve_field(md, "tags")
    if tags is not None and (not isinstance(tags, list) or not tags):
        errors.append(f"{skill.path}: 'tags' must be a non-empty list")

    compatibility = resolve_field(md, "compatibility")
    if compatibility is not None and (not isinstance(compatibility, list) or not compatibility):
        errors.append(f"{skill.path}: 'compatibility' must be a non-empty list")

    last_updated = str(resolve_field(md, "last_updated") or "")
    if last_updated and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_updated):
        errors.append(
            f"{skill.path}: 'last_updated' must use YYYY-MM-DD, got '{last_updated}'"
        )


def validate_structure(skill: Skill, max_lines: int, errors: List[str]) -> None:
    if skill.line_count > max_lines:
        errors.append(
            f"{skill.path}: line count {skill.line_count} exceeds max {max_lines}"
        )

    h2_headings = extract_h2_headings(skill.body)
    for heading in REQUIRED_H2_HEADINGS:
        if heading not in h2_headings:
            errors.append(f"{skill.path}: missing required H2 heading '## {heading}'")

    if not has_feedback_loop_section(skill.body):
        errors.append(f"{skill.path}: missing explicit 'Feedback Loop' section")


def route_score(prompt_tokens: set, skill: Skill) -> int:
    score = 0
    folder_tokens = set(skill.folder.split("-"))
    name_tokens = tokenize(str(skill.metadata.get("name", "")))
    hints = set(SKILL_HINTS.get(skill.folder, []))

    for token in prompt_tokens:
        if token in skill.profile_tokens:
            score += 1
        if token in hints:
            score += 2
        if token in folder_tokens or token in name_tokens:
            score += 2

    return score


def validate_routing(skills: List[Skill], cases_path: Path, errors: List[str]) -> None:
    if not cases_path.exists():
        errors.append(f"Missing cases file: {cases_path}")
        return

    try:
        cases_data = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        errors.append(f"{cases_path}: invalid YAML ({exc})")
        return
    if not isinstance(cases_data, dict) or not isinstance(cases_data.get("cases"), list):
        errors.append(f"{cases_path}: expected top-level 'cases' list")
        return

    cases = cases_data["cases"]
    covered_skills = set()
    skills_by_folder = {s.folder: s for s in skills}

    for case in cases:
        if not isinstance(case, dict):
            errors.append(f"{cases_path}: case must be a mapping, got '{case}'")
            continue

        case_id = case.get("id", "<unknown>")
        prompt = str(case.get("prompt", "")).strip()
        expected = str(case.get("expected_skill", "")).strip()

        if not expected:
            errors.append(f"{cases_path}: case '{case_id}' missing expected_skill")
            continue

        if expected not in skills_by_folder:
            errors.append(f"{cases_path}: case '{case_id}' expects unknown skill '{expected}'")
            continue

        # Count declared skill coverage once expected_skill is valid.
        covered_skills.add(expected)

        if not prompt:
            errors.append(f"{cases_path}: case '{case_id}' missing prompt")
            continue

        forbidden_raw = case.get("forbidden_skills", [])
        if forbidden_raw is None:
            forbidden = []
        elif not isinstance(forbidden_raw, list):
            errors.append(
                f"{cases_path}: case '{case_id}' field 'forbidden_skills' must be a list of skill names"
            )
            continue
        else:
            invalid_forbidden = [
                item for item in forbidden_raw if not isinstance(item, str) or not item.strip()
            ]
            if invalid_forbidden:
                errors.append(
                    f"{cases_path}: case '{case_id}' has invalid forbidden_skills entries: {invalid_forbidden}"
                )
                continue
            forbidden = [item.strip() for item in forbidden_raw]

        unknown_forbidden = [item for item in forbidden if item not in skills_by_folder]
        if unknown_forbidden:
            errors.append(
                f"{cases_path}: case '{case_id}' has unknown forbidden skills: {unknown_forbidden}"
            )
            continue

        prompt_tokens = tokenize(prompt)
        scored = []
        for skill in skills:
            score = route_score(prompt_tokens, skill)
            scored.append((score, skill.folder))
        scored.sort(key=lambda x: (-x[0], x[1]))

        top_score, predicted = scored[0]
        if top_score == 0:
            errors.append(f"{cases_path}: case '{case_id}' produced zero scores for all skills")
            continue

        if predicted != expected:
            errors.append(
                f"{cases_path}: case '{case_id}' routed to '{predicted}' (score {top_score}) "
                f"instead of '{expected}'"
            )

        for forbidden_skill in forbidden:
            if predicted == forbidden_skill:
                errors.append(
                    f"{cases_path}: case '{case_id}' predicted forbidden skill '{forbidden_skill}'"
                )

    missing_coverage = sorted(set(skills_by_folder) - covered_skills)
    if missing_coverage:
        errors.append(
            f"{cases_path}: regression cases missing coverage for skills: {', '.join(missing_coverage)}"
        )


def discover_skills(skills_dir: Path, errors: List[str]) -> List[Skill]:
    skills = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            skills.append(build_skill(path))
        except Exception as exc:
            errors.append(f"{path}: failed to parse SKILL.md ({exc})")
    return skills


def main() -> int:
    parser = argparse.ArgumentParser(description="Run skill metadata and routing regressions")
    parser.add_argument("--skills-dir", default="agents", help="Directory containing skill folders")
    parser.add_argument(
        "--cases",
        default=str(Path(__file__).with_name("skill-regression-cases.yaml")),
        help="YAML file containing routing regression cases",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=500,
        help="Maximum allowed lines per SKILL.md",
    )
    args = parser.parse_args()

    skills_dir = Path(args.skills_dir)
    cases_path = Path(args.cases)

    if not skills_dir.exists():
        print(f"[ERROR] Skills directory not found: {skills_dir}")
        return 2

    errors: List[str] = []
    skills = discover_skills(skills_dir, errors)
    if not skills:
        if errors:
            print("[FAIL] Skill regression checks failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
        print(f"[ERROR] No SKILL.md files found under {skills_dir}")
        return 2

    seen_names = {}
    for skill in skills:
        validate_metadata(skill, errors)
        validate_structure(skill, args.max_lines, errors)

        name = str(skill.metadata.get("name", "")).strip()
        if name:
            if name in seen_names:
                errors.append(
                    f"Duplicate frontmatter name '{name}' in {skill.path} and {seen_names[name]}"
                )
            else:
                seen_names[name] = skill.path

    if not any("failed to parse SKILL.md" in error for error in errors):
        validate_routing(skills, cases_path, errors)

    if errors:
        print("[FAIL] Skill regression checks failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        f"[PASS] Skill regression checks passed for {len(skills)} skills "
        f"(max_lines={args.max_lines}, cases={cases_path})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
