# Symbol-Grounded Geometry Figure Benchmark — North Star Spec

## Scope
- Dataset: 20 base Euclidean geometry items across five diagnostic categories.
- Contrastive variants per base item: mark toggle/remove, label nudge/swap, rotation, text-only, image-only.
- Symbol-grounding: every decisive mark represented explicitly in scene graph and annotations.
- Process-level metrics: answer accuracy, grounding precision/recall/F1, contrastive consistency, error codes (GP, TG, AC, LC, NS).

## Categories
1. Tangent–secant (external angle; tangent ⟂ radius).
2. Arc vs chord vs central/inscribed angle distinctions.
3. Invented parallels/perpendiculars (similarity traps).
4. Label anchoring (leader lines, midpoints, swapped labels).
5. Not-to-scale drawings versus marked equality.

## Deliverables
- `items/<ID>/`: prompt, scene YAML, rendered assets, gold answers, PGDP annotations, variant metadata.
- `schema/scene.schema.json`: source-of-truth schema for primitives, symbols, links, metadata.
- `tools/`: deterministic SVG/PNG renderer, variant generator, validators.
- `eval/`: evaluation harness computing metrics and tagging error codes.
- `docs/`: dataset card, case studies, quickstart after MVP.

## Prompt Contract
```
Problem:
<text>

Instructions:
- Do NOT assume figures are to scale.
- Use ONLY marks visible in the diagram unless explicitly stated in the text.
- Follow the output contract below exactly.

RESPONSE FORMAT (mandatory):
FINAL_ANSWER: <value + unit>

FIGURE_FACTS_USED:
- <...>

TEXT_GIVENS_USED:
- <...>

ASSUMPTIONS:
- none|<list>
```

## Definitions of Done
- Spec referenced by tooling and documentation.
- All dataset scripts accept paths/configs defined here.
- Any change to scope requires spec update and review.


### IDs & Naming (Required)
Item IDs: T1 … T20 (category letter optional), immutable after release.
Variant IDs: {itemId}_{type}, where {type} ∈ {full_txtimg, img_only, txt_only, adversarial, mark_removed, toggle_parallel, label_nudge, label_swap, rotate}.
Symbol IDs: human‑readable, e.g., par1_AB_CD, perp1_OT_PA, tick1_AB, arcA_AB, tangA.
File naming:
Base: <ID>.svg, <ID>_{96,144,300}.png, <ID>.gold.json, <ID>.pgdp.json, <ID>.variants.json.
Variant images append op names: e.g., T3_rot10_96.png, T3_no_tangent_144.png.


### Variant Semantics
mark_removed: remove exactly one decisive symbol (defined below). Must cause the answer to flip or become indeterminate.
toggle_parallel(L1,L2): add/remove ∥ mark between lines; only used when similarity/angle relations hinge on it.
label_nudge(text_id, dx, dy): move rendered label by 5–8 px; the anchor point stays fixed.
label_swap(t1,t2): swap two text labels; anchors remain with their geometry points.
adversarial: rotate ±10°, thin symbol opacity to 40–60%, and export at 96 DPI.
img_only / txt_only:
IMG‑only: prompt includes no decisive text givens; diagram conveys the key marks.
TXT‑only: text includes decisive givens; no image provided.
Invariant: cosmetic variants (rotate/thin/raster) must not change the gold answer.


### Scene Graph Invariants
Coordinates in pixels; origin at top‑left; y increases downward.
Layers: primitives (points/lines/circles/arcs), symbols (angle_arc, tick_bar, parallel, perpendicular, tangent_mark), labels.
Links: every symbol has sym2geo; every measured text has text2geo.
Arc vs chord are distinct primitive types; arcs carry angular measure (measure_deg), lines carry length only if stated.
Tangency relation is explicit: tangent: [{line: PA, at: A}].


### Decisive Mark Contract
Each base item lists decisive_symbol_id.
Its removal/toggle must alter the answer or yield “indeterminate”.
Unit test: flip_or_indeterminate(item_id) must pass prior to release.


### Prompt Contract (clarifications)
Units: all angles in degrees; lengths in arbitrary units if used.
FIGURE_FACTS_USED must include only facts visible in the image (e.g., “OT ⟂ PA”, “arc AB = 110° (near‑arc label)”).
TEXT_GIVENS_USED includes only statements explicitly present in the prompt text.
ASSUMPTIONS must be “none” for full process credit.


### Grounding & Contrastive Metrics
Grounding P/R/F1: compare FIGURE_FACTS_USED (normalized) with the figure truth set extracted from *.pgdp.json.
Invented fact: any claimed ∥/⟂/equality/arc measure not present in pgdp.json and not in TEXT_GIVENS_USED → GP.
Contrastive Consistency: for variants marked expected_effect = "flip_or_invalidate", the predicted answer must differ from the base or return “indeterminate”.


### Error Codes
GP — guessed parallels/perpendiculars or equalities not present as marks or text givens.
TG — missed radius⊥tangent fact when present.
AC — arc↔chord confusion (claimed arc measure when only chord is labeled, or vice‑versa).
LC — label anchoring error (used label position rather than leader/anchor).
NS — reliance on visual scale (“looks equal/isosceles”).


### File Layout Guarantees
Each items/<ID>/ contains:
prompt.txt, scene.yaml, *.svg, *_{96,144,300}.png, *.gold.json, *.pgdp.json, *.variants.json.
All JSON/YAML files validate against schemas in /schema.


### Licensing & Versioning
Data: CC BY 4.0 (recommended) or CC BY‑SA 4.0.
Code: MIT or Apache‑2.0.
Semantic versioning. MVD release is v0.1.0.