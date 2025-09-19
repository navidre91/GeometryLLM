# Dataset Card (skeleton)

**Name**: Geometry Figure Grounding (micro-suite)  
**Version**: 0.1.0

## Motivation
VLMs often misread fine‑grained diagram marks (ticks, angle arcs, ⟂, ∥, tangency) and rely on visual scale. This suite isolates **figure perception** from **reasoning** by supplying symbol‑grounded figures with **contrastive** edits that must flip or invalidate answers.

## Composition
- 20 base items (target), 5 variants each (Full, IMG‑only, TXT‑only, Adversarial, Mark‑Removed).  
- Each figure has a **scene graph** (primitives, symbols, labels), layered SVG/PNGs, gold, and PGDP‑style annotations.

## Annotations
- `sym2geo` and `text2geo` links provide machine‑verifiable grounding of marks and labels.
- Gold includes answer value/tolerance, reasoning keys, and error tags.

## Intended use
Research on multimodal mathematical reasoning and diagram grounding.

## Known limitations
- Grounding comparison uses string normalization; it assumes the model adheres to the prompt contract.
- Renderer covers common symbols; exotic constructions may require glyph extensions.
