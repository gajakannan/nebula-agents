# Product Manager Scripts

Generic scripts for validating stories and generating indexes.

Story convention:
- One story per markdown file.

## validate-stories.py

Validate one or more story files:

```bash
python agents/product-manager/scripts/validate-stories.py {PRODUCT_ROOT}/planning-mds/features/F0001-dashboard/F0001-S0001-view-kpis.md
python agents/product-manager/scripts/validate-stories.py {PRODUCT_ROOT}/planning-mds/features/F0001-dashboard/F0001-S0001-view-kpis.md {PRODUCT_ROOT}/planning-mds/features/F0001-dashboard/F0001-S0002-view-pipeline.md
```

Validate a directory of stories:

```bash
python agents/product-manager/scripts/validate-stories.py {PRODUCT_ROOT}/planning-mds/features/
```

## generate-story-index.py

Generate a story index for a directory:

```bash
python agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/
```

Outputs `{PRODUCT_ROOT}/planning-mds/features/STORY-INDEX.md`.

## validate-trackers.py

Validate tracker consistency across `REGISTRY.md`, `ROADMAP.md`, `STORY-INDEX.md`, and `BLUEPRINT.md`.
Also validates `STATUS.md` closeout signoff governance for features marked `Done`/`Archived`:
- required signoff matrix exists
- baseline required roles (`Quality Engineer`, `Code Reviewer`) are marked required
- required roles have story-level passing provenance entries with reviewer/date/evidence
- PASS evidence cannot reference `agents/**`; it must point to solution artifacts

```bash
python3 agents/product-manager/scripts/validate-trackers.py
python3 agents/product-manager/scripts/validate-trackers.py --features-dir {PRODUCT_ROOT}/planning-mds/features --blueprint {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md
```
