# ARCHITECTURE.md — Symbol‑Grounded Geometry Benchmark

This document is a **map of the codebase**: what the `schema/` folder guarantees and *what each module/function is responsible for*. It’s concise by design—use it as a checklist when you (or a code‑gen agent) add features.

---

## 1) Big Picture

**Goal:** evaluate whether models truly *read the diagram* (marks, labels) vs. guessing from text/scale.

**Flow:**  
1) Author `items/<ID>/scene.yaml` (single source of truth).  
2) `tools/render_svg.py` → layered SVG + PNGs + `*.pgdp.json` (symbol‑aware annotations).  
3) `tools/make_variants.py` → contrastive/modality variants (e.g., mark‑removed, rotate).  
4) `tools/validate_gold.py` → schema & linkage QA.  
5) `eval/evaluate.py` → Answer accuracy **and** Grounding P/R/F1 + Contrastive Consistency + error flags.

---

## 2) Data Contracts — `schema/` folder

These JSON Schemas define the **shape of data** that all tooling trusts.

- **`schema/scene.schema.json`**  
  Contract for a drawable scene:
  - `points[]` with pixel coordinates.  
  - `primitives[]` one of: **Line**, **Circle**, **Arc**.  
  - `symbols[]` one of: **angle_arc**, **tick_bar**, **parallel**, **perpendicular**, **tangent_mark** (IDs are stable).  
  - `texts[]` with `string`, `anchor` (geometry ID), optional `offset`.  
  - `relations[]` links: **`sym2geo`** (symbol → primitives), **`text2geo`** (text → target, e.g., angle arc).  
  - `givens` (optional structured givens), `ask` (target), and embedded `gold` (minimal answer + keys + tags).

- **`schema/gold.schema.json`**  
  Gold answer format: numeric value (+ optional tolerance), plus `reasoning_keys[]` and `error_tags[]`.

- **`schema/variants.schema.json`**  
  Contrastive/modality variants: `variant_id`, whether text is included, image path, `render_ops[]`, `mark_removed[]`, `expected_effect`, `decisive_symbol`.

- **`schema/response.schema.json`**  
  Model response contract for process‑level eval: `final_answer`, `figure_facts_used[]`, `text_givens_used[]`, `assumptions[]`, optional `explanation`.

> **Why schemas?** They make the pipeline deterministic and debuggable: any drift breaks fast in validation—not later during evaluation.

---

## 3) Rendering & Variants — `tools/`

### `tools/render_svg.py`
Build deterministic, layered SVG/PNGs and export PGDP‑style annotations.

- `load_json(path)` / `load_yaml(path)` — file readers.
- `try_validate_scene(scene, schema_path)` — soft‑validate scene against schema (warn; do not crash).
- `points_dict(scene)` — map point IDs → `(x, y)`.
- `find_primitive(scene, id)` — return primitive dict by ID.
- `find_line_pts(scene, line_id)` — return two endpoints for a Line primitive.
- `line_intersection(p1,p2,p3,p4)` — intersection of two infinite lines (for ⟂ square placement).
- `svg_header(width,height,root_id)` / `svg_footer()` — SVG wrapper with CSS classes.
- `draw_primitives(scene)` — render `<g id="primitives">` (Circles/Lines/Arcs) and infer canvas size.
- `unit_vec(dx,dy)` / `perp_vec(dx,dy)` — tiny vector helpers for glyph placement.
- `draw_symbol_angle_arc(scene, sym)` — small angle arc from two lines at a vertex.
- `draw_symbol_perpendicular(scene, sym)` — tiny right‑angle square at line intersection.
- `draw_symbol_parallel(scene, sym)` — short double chevrons on two lines.
- `draw_symbol_tangent(scene, sym)` — miniature tangency “⊥” near a point.
- `draw_symbol_tick_bar(scene, sym)` — short tick across a line midpoint.
- `draw_symbols(scene, opacity)` — render `<g id="symbols">` (dispatch to glyph functions).
- `draw_labels(scene)` — render `<g id="labels">` (point dots + labels; `measure` class for degree text).
- `wrap_rotation(svg_inner, width, height, angle_deg)` — optional group rotation (adversarial).
- `export_pngs(svg_path, base_name)` — rasterize to 96/144/300 DPI (CairoSVG).
- `main()` — CLI glue: read scene → (soft) validate → compose SVG → write `<ID>.svg`, `<ID>.pgdp.json`, PNGs.

### `tools/make_variants.py`
Apply contrastive/cosmetic ops, re‑render, and name the outputs per `variants.json`.

- `load_json(path)` / `load_yaml(path)` / `save_yaml(obj,path)` — IO helpers.
- `remove_symbol_or_text(scene, id)` — remove a symbol or text **and** its relations.
- `nudge_label(scene, text_id, dx, dy)` — change label `offset`; **anchor stays attached**.
- `swap_labels(scene, t1, t2)` — swap **string contents** of two texts.
- `apply_ops(scene, ops)` — parse/execute `render_ops` (e.g., `rotate10`, `thin_symbols`, `nudge:…`, `remove_symbol:…`); return modified scene + render params.
- `call_renderer(scene_path, out_dir, rotate, symbol_opacity)` — call `render_svg.py` from repo root.
- `main()` — iterate variants: apply `mark_removed` + `render_ops`, re‑render, rename output image if requested.

### `tools/validate_gold.py`
Fail‑fast sanity checks before publishing/evaluating.

- `load_json(path)` / `load_yaml(path)` — IO helpers.
- `validate_scene(scene_path, schema_path)` — schema validation; ensures:
  - every **symbol** has a `sym2geo` link, and  
  - every **degree text** (e.g., “31°”) has a `text2geo` link.
- `validate_variants(scene_path, variants_path)` — each variant’s `decisive_symbol` exists in base scene (symbol or text).
- `main()` — walk `items/*`, run checks, print status, exit non‑zero on errors.

---

## 4) Evaluation — `eval/`

### `eval/evaluate.py`
Compute metrics and tag canonical failure modes.

- `load_json(path)` — read JSON.
- `parse_number(s)` — first numeric from `final_answer` for tolerance checks.
- `normalize_fact(s)` — canonicalize claims: “perpendicular”→`⊥`, “parallel”→`∥`, “tangent at/to”→`tangent@`, normalize whitespace/case.
- `truth_facts_from_pgdp(pgdp)` — extract ground‑truth figure facts from `*.pgdp.json`:
  - `⊥/∥/tangent@` via `sym2geo`,  
  - `angle = N°` via `text2geo`.
- `grounding_prf(used, truth)` — compute Precision/Recall/F1 on `FIGURE_FACTS_USED`.
- `invented_parallel(used, truth)` — flag **GP** (guessed ∥).
- `tangent_missing(truth, used)` — flag **TG** (missed tangent⊥radius citation).
- `arc_chord_conflict(used, truth)` — flag **AC** (arc↔chord misuse).
- `label_anchor_violation(used)` — flag **LC** (uses label *position* rather than anchor).
- `mentions_visual_scale(text)` — flag **NS** (“looks equal / by scale / visually”).
- `evaluate_variant(item_id, variant, gold, pgdp, resp_path)` — per‑variant Accuracy, Grounding P/R/F1, error flags; returns row + numeric prediction.
- `main()` — iterate items and variants; write `results.csv` and add a **contrastive consistency** check (base vs. mark‑removed).

> Stubs in `eval/validators/*.py` exist for future modularization; current checks live inside `evaluate.py`.

---

## 5) Tests — `tests/`

- `test_scene_schema.py` — every `scene.yaml` validates against `schema/scene.schema.json`.
- `test_render_svg.py` — rendered SVG exists and contains the three groups + key IDs.
- `test_variants_flip.py` — decisive variant declares `decisive_symbol` and `expected_effect: flip_or_invalidate`.
- `test_evaluate.py` — `grounding_prf` returns sensible values on a toy case.

---

## 6) CI & Conveniences

- **Makefile** targets: `install`, `render`, `variants`, `validate`, `eval`, `test`.  
- **.github/workflows/ci.yml**: run the full chain on PRs (render → variants → validate → eval → tests).

---

## 7) Optional: RoMMath Seed Importers — `scripts/` (separate kit)

If you’re using the RoMMath tailored kit:

- `rommath_scraper_tailored.py`
  - `fetch_split_json` — load split JSON from Hugging Face.
  - `build_item_dir` — create `items/<ID>/…`.
  - `resolve_image_url` — compute absolute figure URL.
  - `diagnostic_map` — heuristic mapping into the five diagnostic categories.
  - `main` — write `prompt.txt`, `gold.json`, `source.json`, `external_image_url.txt`, `scene.yaml` (raster stub), `variants.json`, `diagnostic.json`; download image.

- `rommath_offline_demo.py`
  - `main` — build a tiny offline demo from paraphrased examples with the same per‑item layout.

---

## 8) Extend Safely (guidelines)

- **Keep IDs stable.** Symbols/texts in `scene.yaml` must match IDs in SVG and PGDP.
- **Link all marks.** Every symbol gets `sym2geo`; every measured text gets `text2geo`.
- **One decisive edit per item.** Mark‑removed variants must change the answer or make it indeterminate.
- **Process contract matters.** Enforce `FIGURE_FACTS_USED` vs. truth to diagnose grounding—not just the final number.

That’s it—this file is intended to be short and practical. Commit it as `docs/ARCHITECTURE.md`.
