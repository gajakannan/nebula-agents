# Git hooks

Version-controlled hooks for this repo. They are **not** active until you point git at this directory
(git does not auto-run hooks from a tracked folder):

```bash
git config core.hooksPath .githooks
```

Run that once per clone. CI enforces the same checks regardless, so an unactivated hook only means you
find out later, in the PR, instead of at commit time.

## `pre-commit` — KG reproducibility and coverage freshness

Mirrors the product's two knowledge-graph CI gates locally. Both checks read the working tree, so stage
the regenerated files you intend to commit.

1. **`kg_reproducibility`** — `scripts/kg/validate.py --check-reproducible`, when a commit touches
   `planning-mds/kg-source/**`, `planning-mds/knowledge-graph/**`, or `REGISTRY.md`/`ROADMAP.md`/`STORY-INDEX.md`.
   The compiled projections and tracker regions are produced from `planning-mds/kg-source/**` by
   `scripts/kg/compile.py` and must **never be hand-edited**. To fix: edit the shards, run
   `python3 scripts/kg/compile.py` (+ `validate.py --write-coverage-report`, + the framework
   `generate-story-index.py`), and re-stage.
2. **`knowledge_graph_sync`** — the plain `scripts/kg/validate.py`, on every commit (about a second).
   `coverage-report.yaml` stores a hash of each mapped feature folder, source doc and bound code path, so
   editing any of them after the last `--write-coverage-report` makes it stale. `--check-drift` and
   `--check-reproducible` do not catch this. To fix: `python3 scripts/kg/validate.py --write-coverage-report`
   and `git add planning-mds/knowledge-graph/coverage-report.yaml`.

The hook exits quietly if `scripts/kg/validate.py` is not installed yet.

Emergency bypass (discouraged): `git commit --no-verify`, or, for reproducibility only, a
`KG-Reproducibility-Override: <reason>` trailer on the head commit (the CI gate honors the same trailer).
