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
