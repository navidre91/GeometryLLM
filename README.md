# Geometry Figure Grounding Benchmark (Prototype)

See `SPEC.md` for the locked North Star scope. This README tracks the implementation checklist for the MVP dataset and tooling.

## Layout
- `items/` — per-problem assets (prompt, scene YAML, renders, gold answers, variants).
- `schema/` — JSON schemas for scenes, annotations, and config.
- `tools/` — renderer, variant generator, validation scripts.
- `eval/` — evaluation harness and metric utilities.
- `docs/` — dataset card, qualitative case studies, reporting notebooks.

## Status
- [x] Scope frozen in `SPEC.md`.
- [ ] Repository scaffold populated with starter examples.
- [ ] Scene schema drafted and validated.
- [ ] Rendering/variant tooling implemented.
- [ ] Evaluation harness compiling planned metrics.
