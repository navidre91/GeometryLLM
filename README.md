# Geometry Figure Grounding Benchmark (Prototype)

See `SPEC.md` for the locked North Star scope. This README tracks the implementation checklist for the MVP dataset and tooling.

## Layout
- `items/` — per-problem assets (prompt, scene YAML, renders, gold answers, variants).
- `schema/` — JSON schemas for scenes, annotations, and config.
- `tools/` — renderer, variant generator, validation scripts.
- `configs/` — sample configs for batch tools (e.g., raster adversarial edits).
- `eval/` — evaluation harness and metric utilities.
- `docs/` — dataset card, qualitative case studies, reporting notebooks.

## Status
- [x] Scope frozen in `SPEC.md`.
- [ ] Repository scaffold populated with starter examples.
- [ ] Scene schema drafted and validated.
- [ ] Rendering/variant tooling implemented.
- [ ] Evaluation harness compiling planned metrics.

## Raster Variant Automation

For RoMMath "origin" items that ship as pre-rendered PNGs, use
`tools/make_raster_variants.py` with a YAML config (see
`configs/raster_variants.sample.yaml` for manual edits or
`configs/raster_rotations.yaml` for bulk rotations) to apply pixel-space edits and extend
`variants.json` automatically:

```bash
python tools/make_raster_variants.py \
    --config configs/raster_variants.sample.yaml \
    --items-root out_rommath_origin/items
```

Pass `--dry-run` to preview or `--overwrite` to replace existing assets.
