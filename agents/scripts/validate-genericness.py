#!/usr/bin/env python3
"""
Genericness Validation Script

Prevents solution-specific terms from entering agents/ directory.
Uses an embedded blocked-term list by default. Pass --glossary to use a
product glossary during migration/adaptation work.

Usage:
    python3 agents/scripts/validate-genericness.py [--glossary <path>] [--agents-dir <path>]
    python3 agents/scripts/validate-genericness.py
    python3 agents/scripts/validate-genericness.py --glossary {PRODUCT_ROOT}/planning-mds/domain/glossary.md
"""

import sys
import io
import re
from pathlib import Path


# Static denylist used by default for standalone framework validation.
# Keep this list aligned with the 'Genericness-Blocked Terms' section in
# {PRODUCT_ROOT}/planning-mds/domain/glossary.md for the reference
# insurance-CRM product. Adapters for other domains should supply --glossary.
FALLBACK_BLOCKED_TERMS = [
    "Broker",
    "MGA",
    "Underwriter",
    "Underwriting",
    "Premium",
    "Claim",
    "Insured",
    "Submission",
    "Renewal",
]

# Windows cp1252 stdout can't encode emojis found in scanned files.
# Reconfigure stdout/stderr to utf-8 unconditionally — safe on all platforms.
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def extract_blocked_terms(glossary_path: str) -> list:
    """
    Extract blocked terms from the glossary's 'Genericness-Blocked Terms' section.
    Parses bullet-point entries (- Term) within that section only.
    """
    try:
        content = Path(glossary_path).read_text(encoding='utf-8')
    except Exception as e:
        print(f"[ERROR] Could not read glossary at '{glossary_path}': {e}")
        return []

    terms = []
    in_section = False

    for line in content.split('\n'):
        stripped = line.strip()

        # Detect the target section heading
        if re.match(r'^##\s+Genericness-Blocked Terms', stripped):
            in_section = True
            continue

        # Exit on the next ## section heading
        if in_section and re.match(r'^##\s+', stripped):
            break

        # Parse bullet entries within the section
        if in_section:
            match = re.match(r'^-\s+(.+)$', stripped)
            if match:
                terms.append(match.group(1).strip())

    return terms


def expand_term_variants(term: str) -> set:
    """
    Expand a blocked term to include a basic plural/inflection variant.

    Examples:
    - broker -> brokers
    - submission -> submissions
    - policy -> policies
    """
    base = term.lower().strip()
    variants = {base}

    # Only apply inflection logic to simple alphabetic terms.
    if not re.fullmatch(r'[a-z]+', base):
        return variants

    if base.endswith('y') and len(base) > 1 and base[-2] not in 'aeiou':
        variants.add(base[:-1] + 'ies')
    elif base.endswith(('s', 'x', 'z', 'ch', 'sh')):
        variants.add(base + 'es')
    else:
        variants.add(base + 's')

    return variants


def canonicalize_matched_term(term: str, blocked_term_set: set) -> str:
    """
    Normalize a matched token to the base blocked term when it appears in a
    plural/inflected form.
    """
    word = term.lower()
    if word in blocked_term_set:
        return word

    if word.endswith('ies'):
        candidate = word[:-3] + 'y'
        if candidate in blocked_term_set:
            return candidate

    if word.endswith('es'):
        candidate = word[:-2]
        if candidate in blocked_term_set:
            return candidate

    if word.endswith('s'):
        candidate = word[:-1]
        if candidate in blocked_term_set:
            return candidate

    return word


def scan_directory(agents_dir: str, terms: list) -> list:
    """
    Scan agents/ for occurrences of blocked terms (case-insensitive, word-boundary),
    including basic plural/inflected variants.
    Returns list of (filepath, line_number, line_content) tuples.
    """
    agents_path = Path(agents_dir)
    if not agents_path.is_dir():
        print(f"[ERROR] Directory not found: {agents_dir}")
        return []

    blocked_terms = sorted({term.lower().strip() for term in terms if term.strip()})
    blocked_term_set = set(blocked_terms)
    pattern_terms = sorted(
        {variant for term in blocked_terms for variant in expand_term_variants(term)},
        key=len,
        reverse=True,
    )

    # Case-insensitive word-boundary pattern.
    pattern = re.compile(
        r'\b(' + '|'.join(re.escape(t) for t in pattern_terms) + r')\b',
        re.IGNORECASE
    )

    # Files explicitly allowed to contain blocked terms
    skip_files = {'TECH-STACK-ADAPTATION.md', Path(__file__).name}

    # Term-scoped exception rules for legitimate generic usage.
    # Each blocked term has to be covered by an explicit rule to skip a line.
    term_exception_patterns = {
        'broker': [
            re.compile(r'\bpact broker\b', re.IGNORECASE),
            re.compile(r'\bmessage broker\b', re.IGNORECASE),
        ],
        'submission': [
            re.compile(r'\bform submission\b', re.IGNORECASE),
        ],
        'renewal': [
            re.compile(r'\btoken renewal\b', re.IGNORECASE),
        ],
        'claim': [
            re.compile(r'\bnew\s+claim\s*\(', re.IGNORECASE),
            re.compile(r'\bclaim\s*\(', re.IGNORECASE),
            re.compile(r'\bjwt\s+claims?\b', re.IGNORECASE),
            re.compile(r'\btoken\s+claims?\b', re.IGNORECASE),
            re.compile(r'\bidentity\s+claims?\b', re.IGNORECASE),
        ],
    }

    # Scan all text files in agents/
    extensions = {'.md', '.py', '.sh', '.yaml', '.yml'}
    violations = []

    for file_path in sorted(agents_path.rglob('*')):
        if not file_path.is_file():
            continue
        if file_path.suffix not in extensions:
            continue
        if file_path.name in skip_files:
            continue
        if '.git' in file_path.parts:
            continue

        try:
            lines = file_path.read_text(encoding='utf-8').splitlines()
        except Exception:
            continue

        for line_num, line in enumerate(lines, start=1):
            matches = list(pattern.finditer(line))
            if not matches:
                continue

            matched_terms = {
                canonicalize_matched_term(m.group(0), blocked_term_set)
                for m in matches
            }
            all_terms_exempted = True

            # Boundary gate must remain strict: only skip when each matched
            # blocked term is explicitly exempted by a scoped regex rule.
            for term in matched_terms:
                term_rules = term_exception_patterns.get(term, [])
                if not any(rule.search(line) for rule in term_rules):
                    all_terms_exempted = False
                    break

            if all_terms_exempted:
                continue

            violations.append((str(file_path), line_num, line.strip()))

    return violations


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Validate that agents/ contains no solution-specific terms'
    )
    parser.add_argument(
        '--glossary',
        default=None,
        help='Optional path to domain glossary (default: embedded framework denylist)'
    )
    parser.add_argument(
        '--agents-dir',
        default='agents',
        help='Path to agents directory to scan'
    )
    args = parser.parse_args()

    glossary_path = args.glossary

    print(f"Validating genericness of {args.agents_dir}/")
    print("-" * 60)
    print(f"[Scope]  Scanning only:       {args.agents_dir}/")
    print("[Scope]  Not scanned:          {PRODUCT_ROOT}/planning-mds/ (solution-specific content is allowed)\n")

    # Use the embedded denylist by default so nebula-agents validates
    # standalone. A product glossary is only consulted when explicitly passed.
    if glossary_path and Path(glossary_path).exists():
        blocked_terms = extract_blocked_terms(glossary_path)
        glossary_source_label = glossary_path
    else:
        blocked_terms = []

    if not blocked_terms:
        blocked_terms = list(FALLBACK_BLOCKED_TERMS)
        glossary_source_label = "embedded fallback denylist (agents/scripts/validate-genericness.py)"
        print(f"[Info] Using embedded fallback denylist ({len(blocked_terms)} terms); pass --glossary to override.")

    print(f"[Terms]  {len(blocked_terms)} blocked term(s): {', '.join(blocked_terms)}")
    print(f"[Source] Term list from:      {glossary_source_label}")
    print("[Note]   Source file is used only to derive denylist terms for agents/ validation.\n")

    # Scan
    violations = scan_directory(args.agents_dir, blocked_terms)

    if not violations:
        print("[PASS] agents/ directory is generic — no blocked terms found")
        sys.exit(0)

    # Report violations grouped by file
    print(f"[FAIL] Solution-specific terms found ({len(violations)} hit(s)):\n")

    current_file = None
    for filepath, line_num, line_content in violations:
        if filepath != current_file:
            current_file = filepath
            print(f"  {filepath}")
        print(f"    {line_num}: {line_content}")

    sys.exit(1)


if __name__ == "__main__":
    main()
