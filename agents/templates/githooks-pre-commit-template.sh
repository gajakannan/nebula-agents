#!/usr/bin/env bash
# Local mirror of the product's two knowledge-graph CI gates:
#
#   kg_reproducibility    scripts/kg/validate.py --check-reproducible
#       The compiled KG projections + tracker regions
#         planning-mds/knowledge-graph/{canonical-nodes,feature-mappings,code-index,solution-ontology}.yaml,
#         planning-mds/features/{REGISTRY,ROADMAP,STORY-INDEX}.md
#       are generated from planning-mds/kg-source/** by scripts/kg/compile.py and are NEVER hand-edited.
#   knowledge_graph_sync  scripts/kg/validate.py
#       Integrity plus coverage-report.yaml freshness. The report stores a hash of every mapped feature
#       folder, source doc and bound code path, so editing any of them after the last
#       --write-coverage-report makes it stale. --check-drift and --check-reproducible do not check this.
#
# Both checks read the working tree, not the index: stage the regenerated files you want to commit.
#
# Activate once per clone:   git config core.hooksPath .githooks
# See .githooks/README.md.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if [ ! -f scripts/kg/validate.py ]; then
  exit 0  # KG toolchain not installed yet
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "pre-commit: python3 not found; skipping KG checks (CI will still enforce them)." >&2
  exit 0
fi

staged="$(git diff --cached --name-only --diff-filter=ACMRD)"
if [ -z "$staged" ]; then
  exit 0
fi

# 1. Reproducibility: only when the commit touches the KG source or a generated surface.
if printf '%s\n' "$staged" | grep -qE \
  '^planning-mds/(kg-source/|knowledge-graph/)|^planning-mds/features/(REGISTRY|ROADMAP|STORY-INDEX)\.md$'; then
  echo "pre-commit: verifying KG reproducibility (committed generated files must equal compile(source))…"
  if ! python3 scripts/kg/validate.py --check-reproducible; then
    cat >&2 <<'MSG'

  ✗ KG reproducibility check FAILED — commit blocked.

  The knowledge-graph projections and REGISTRY/ROADMAP/STORY-INDEX regions are COMPILED
  from planning-mds/kg-source/** and must never be hand-edited. Fix by editing the SHARDS,
  then regenerate and re-stage:

      python3 scripts/kg/compile.py                    # trio + ontology + REGISTRY/ROADMAP regions
      python3 scripts/kg/validate.py --write-coverage-report
      # STORY-INDEX (framework script): .../agents/product-manager/scripts/generate-story-index.py planning-mds/features/
      git add -u planning-mds/knowledge-graph planning-mds/features

  (If the checker can't run, ensure deps: pip install pyyaml jsonschema.)
  Emergency bypass (discouraged): git commit --no-verify, or add a
  'KG-Reproducibility-Override: <reason>' trailer to the head commit.

MSG
    exit 1
  fi
  echo "pre-commit: KG reproducibility OK."
fi

# 2. Integrity and coverage freshness: every commit (about a second), because any planning
#    doc or bound code path can stale coverage-report.yaml.
if ! output="$(python3 scripts/kg/validate.py 2>&1)"; then
  printf '%s\n' "$output" | sed -n '/^Errors:/,$p' >&2
  cat >&2 <<'MSG'

  ✗ KG validation FAILED — commit blocked (CI gate: knowledge_graph_sync).

  If the error is "coverage-report.yaml is stale", a mapped doc or bound path changed after
  the last coverage write. Regenerate and stage it:

      python3 scripts/kg/validate.py --write-coverage-report
      git add planning-mds/knowledge-graph/coverage-report.yaml

  Other errors are real integrity failures: fix the source (shards, paths, refs), recompile,
  and re-run python3 scripts/kg/validate.py.
  Emergency bypass (discouraged): git commit --no-verify.

MSG
  exit 1
fi
echo "pre-commit: KG validation OK."
