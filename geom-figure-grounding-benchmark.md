# Symbol‑Grounded Geometry Figure Benchmark
**A step‑by‑step implementation guide focusing only on the novel parts (symbol‑grounding, contrastive figure edits, and process‑level evaluation).**  
Version: 1.0 • Date: 2025‑09‑18

---

## Motivation

Multimodal LLMs often “solve” geometry problems without truly reading the diagram. They **hallucinate** parallels, rely on **visual scale** in not‑to‑scale drawings, or confuse **arcs/chords/tangents**. Existing benchmarks largely report **final‑answer accuracy**, which blurs two distinct capabilities:

1) **Figure perception** — Did the model correctly parse the fine‑grained diagram signals (tick marks, angle arcs, ⟂ squares, ∥ chevrons, tangent points, label leader lines)?  
2) **Reasoning** — Given those signals, did it perform valid Euclidean reasoning to reach the answer?

This guide specifies a small but **diagnostic** benchmark that isolates figure‑reading from reasoning via:
- **Symbol‑grounded figures** with machine‑readable annotations;  
- **Contrastive edits** (toggle/remove a decisive mark or nudge/swap labels) that **must** flip the correct answer or invalidate it;  
- **Process‑level scoring**: models must list the **figure facts used**; we score **grounding Precision/Recall** against the actual marks present and flag canonical errors (e.g., **GP** guessed parallel).

The document is written for direct ingestion by another LLM (or a human engineer). It includes schemas, file layouts, prompts, pseudocode, and **definitions of done** for each step.

---

## Scope & Novel Contributions (deliverables)

1. **Dataset (micro‑suite):** ~20 base Euclidean‑geometry items across 5 error‑prone categories, each with **contrastive variants** (mark‑removed/mark‑toggled, label‑nudged, rotated, text‑only, image‑only).  
2. **Symbol‑aware annotations:** PGDP‑style **primitive**+**symbol** scene graphs exported directly from the renderer (no manual pixel labeling).  
3. **Process‑level evaluation:** Answer accuracy **and** **Grounding P/R/F1**, **Contrastive Consistency**, and **error codes**:  
   - **GP** (guessed parallels/perpendiculars), **TG** (forgot tangent⊥radius), **AC** (arc↔chord confusion), **LC** (label anchoring confusion), **NS** (trusted visual scale).  
4. **Turn‑key harness & schemas:** JSON/YAML schemas, reference evaluator, unit tests, and a minimal **8‑item tangent–secant** starter set.

> Everything else (generic adversarial noise, large‑scale scraping, formal theorem proving) is intentionally out of scope to keep focus on novelty.

---

## Quick Start (TL;DR)

1. **Clone repo** and create the folders shown in [Repository Layout](#repository-layout).  
2. **Author scenes** in `scene.yaml` for ~20 items using the schema in [Scene Graph Schema](#scene-graph-schema).  
3. **Render SVG/PNG** with `tools/render_svg.py` (IDs on all primitives & symbols).  
4. **Generate variants** with `tools/make_variants.py` (mark toggle/remove, label nudge/swap, rotation, DPI).  
5. **Define gold** answers + reasoning keys (`*.gold.json`) and **export PGDP‑like annotations** (`*.pgdp.json`).  
6. **Evaluate** with `eval/evaluate.py` to compute **Accuracy**, **Grounding P/R/F1**, **Contrastive Consistency**, and **error codes**.  
7. **Report** per‑category results and two qualitative case studies.

---

## Step‑by‑Step Roadmap (novelty‑only)

### Step 0 — Pin down the one‑page spec (North Star)
**Goal:** Freeze what’s in/out to protect novelty.  
**Deliverables:** A one‑pager listing: dataset size (~20 base items), 5 categories, symbol‑grounding requirement, contrastive edits, process metrics, fixed prompt format.  
**Definition of Done:** A committed `SPEC.md` referenced by all scripts.

---

### Step 1 — Data collection (targeted prompts, draw your own figures)
**Goal:** Curate **20 base items** across 5 categories (4 each):
- Tangent–secant (external angle; radius⊥tangent),  
- Arc vs chord vs central/inscribed,  
- Invented ∥/⟂ (similarity traps),  
- Label anchoring (leader lines, midpoints),  
- Not‑to‑scale vs marked equality.

**Checklist per item:**
- [ ] Exactly one **decisive** mark/label exists whose addition/removal **changes** the answer (or makes it “indeterminate”).  
- [ ] No alternate solution bypasses that mark.  
- [ ] Unique numeric/symbolic answer.  
- [ ] Short, neutral text (avoid giving away the decisive mark unless in the **TXT‑only** variant).

**Deliverables:** `items/<ID>/prompt.txt` (base statement & question).

---

### Step 2 — Scene Graph Schema
**Goal:** A single **source‑of‑truth** used to both render the SVG/PNG and export the annotations. (No manual pixel labels.)

See [Scene Graph Schema](#scene-graph-schema) with a worked example.  
**Deliverables:** `schema/scene.schema.json` and `items/<ID>/scene.yaml`.  
**Definition of Done:** Re‑rendering the same `scene.yaml` is pixel‑identical and re‑exports the same annotations.

---

### Step 3 — Renderer (SVG‑first)
**Goal:** Deterministic renderer that produces **layered** SVG (primitives / symbols / labels). Export PNG at 96/144/300 DPI.

**Requirements:**
- Stable IDs on every primitive (`Point`, `Line`, `Circle`, `Arc`) and symbol (`angle_arc`, `tick_bar`, `parallel`, `perpendicular`, `tangent_mark`).  
- Label anchor is the **geometry point**, not the text glyph position.  
- Small, reusable symbol glyphs (mini‑paths) for arcs, ticks, ⟂ squares, ∥ chevrons.

**Deliverables:** `tools/render_svg.py`.  
**Definition of Done:** `validate_gold.py` confirms every symbol is linked (`sym2geo`) to its target primitives.

---

### Step 4 — Contrastive Variant Generator
**Goal:** **Programmatically** flip or invalidate answers with minimal visual edits.

**Core transforms (composable):**
- `toggle_mark("parallel", L1, L2)`  
- `remove_symbol(sym_id)` (delete one tick/arc/⟂)  
- `nudge_label(text_id, dx, dy)` (5–8 px; point stays fixed)  
- `swap_labels(text_id1, text_id2)`  
- `rotate_canvas(theta)` (±10°)  
- `thin_symbols(opacity=0.4–0.6)` (symbols layer only)  
- `rasterize(dpi)` (96/144/300)

**Deliverables:** `tools/make_variants.py`, `items/<ID>/<ID>.variants.json`.  
**Definition of Done:** Unit tests verify that **decisive** edits flip the gold answer or make it “not determinable”.

---

### Step 5 — Gold, Reasoning Keys, and PGDP‑style Annotations
**Goal:** Bind the item to ground‑truth answer and machine‑verifiable figure facts.

**Files per item:**
- `items/<ID>/<ID>.gold.json` — numeric answer (+ tolerance), `reasoning_keys`, `error_tags`.  
- `items/<ID>/<ID>.pgdp.json` — primitive boxes, symbol classes & **relations** (`sym2geo`, `text2geo`).  
- Optional: small recomputation function when flipping a mark changes the math.

**Definition of Done:** `eval/validators/*` can verify: (1) mark presence/absence, (2) tangent⊥radius where declared, (3) arc vs chord labeling consistency.

---

### Step 6 — Prompt that Forces Grounding
**Goal:** Force the model to list only **visible** figure facts (marks/labels), separately from text givens.

**Fixed output contract (models that deviate get 0 on process metrics):**
```
FINAL_ANSWER: <number + unit>

FIGURE_FACTS_USED:
- <only marks visible in the diagram, e.g., "OT ⟂ PA", "arc AB = 110° (near-arc label)">

TEXT_GIVENS_USED:
- <only given statements from the prompt; write "none" if none>

ASSUMPTIONS:
- none
```

**Deliverables:** `items/<ID>/prompt.txt` (with the instruction block).

---

### Step 7 — Repository Layout
```
geom_grounding/
  items/
    T1/
      scene.yaml
      T1.svg  T1_96.png  T1_144.png  T1_300.png
      T1.gold.json
      T1.pgdp.json
      T1.variants.json
      prompt.txt
    ...
  schema/
    scene.schema.json
    gold.schema.json
    variants.schema.json
    response.schema.json
  tools/
    render_svg.py
    make_variants.py
    validate_gold.py
  eval/
    evaluate.py
    validators/
      parallel_check.py
      arc_chord_check.py
      tangent_check.py
      label_anchor_check.py
  README.md
```

---

### Step 8 — Evaluation Harness (metrics that reflect novelty)
**Goal:** Score **what** the model used from the figure, not only **what** it answered.

**Metrics:**
1. **Answer Accuracy** — exact (or within tolerance).  
2. **Grounding Precision / Recall / F1** — compare `FIGURE_FACTS_USED` to the truth set from `*.pgdp.json`.  
3. **Contrastive Consistency** — when a decisive mark is toggled/removed, the answer **must** change or become “not determinable”.  
4. **Variant Sensitivity** — accuracy drop Full→IMG‑only, Full→TXT‑only, Full→Adversarial, Full→Mark‑Removed.  
5. **Process Validity** — presence of `reasoning_keys` in the explanation.

**Canonical error codes (auto‑flagged):**
- **GP** — guessed parallels/perpendiculars not present as symbols or text givens.  
- **TG** — missed tangent⊥radius when present.  
- **AC** — arc↔chord confusion.  
- **LC** — label anchoring error (used label placement, not leader/anchor).  
- **NS** — relied on visual scale (“looks equal/isosceles”).

**Pseudocode skeleton:**
```python
acc = is_correct(pred.answer, gold.answer)
used = normalize_facts(pred.figure_facts_used)
truth = load_truth_facts(pgdp_json)

P, R, F1 = prf(used, truth)

flags = []
if invented_parallel(used, truth): flags.append("GP")
if tangent_missing(truth, used):   flags.append("TG")
if arc_chord_conflict(used, truth):flags.append("AC")
if label_anchor_violation(used, truth): flags.append("LC")
if mentions_visual_scale(pred): flags.append("NS")
```

**Deliverables:** `eval/evaluate.py` and `eval/validators/*.py`.  
**Definition of Done:** Running the harness on the starter set produces a CSV with per‑item metrics and error tags.

---

### Step 9 — Minimal Viable Dataset (MVD)
**Goal:** Prove the concept with a compact yet revealing suite.

- 20 base items (you already have 8 tangent–secant).  
- For each: generate 5 variants — `full_txtimg`, `img_only`, `txt_only`, `adversarial_render`, `mark_removed`.  
- **100 samples total** — enough to show signal without heavy annotation.

**Definition of Done:** Sanity checks pass (below), baselines run, results reported.

---

### Step 10 — Baselines & Ablations
Run at least:
- **One closed VLM** (if accessible) and **one open VLM** (≤7B and 13–34B).  
- **With and without** the self‑report section to quantify **Grounding F1** gains.

Report **per‑category** performance and **error distributions**.

---

### Step 11 — Sanity Checks / QA
1. **Flip test** — for every decisive edit, gold answer flips or becomes “indeterminate”.  
2. **Render parity** — re‑rendering from `scene.yaml` yields identical SVG/PNG and identical `pgdp.json`.  
3. **Annotation completeness** — each symbol has `sym2geo`; each textual measure has `text2geo`.  
4. **Leak check** — **IMG‑only** variants have no decisive mark in text; **TXT‑only** includes it when intended.  
5. **Human ambiguity** — 3 human solvers agree on base answers and that the mark is decisive.

---

### Step 12 — Reporting
Include:
- Table: **Accuracy**, **Grounding F1**, **Contrastive Consistency** by category.  
- Bar plots: variant sensitivity.  
- Two case studies with diagrams (one success, one failure).  
- Short discussion of the **most frequent error codes**.

---

### Step 13 — Release Artifacts
- Dataset card (scope, license for original figures, annotation spec).  
- Scripts: `make_variants.py`, `evaluate.py`, baseline configs.  
- A viewer notebook to overlay **claimed facts vs. ground truth** (green/red).

---

## Scene Graph Schema

Below is a **minimal** schema that’s sufficient to render figures and export symbol‑aware annotations. You may extend as needed.

### JSON Schema (`schema/scene.schema.json`)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Geometry Scene",
  "type": "object",
  "required": ["points", "primitives", "symbols", "texts", "relations", "givens", "ask", "gold"],
  "properties": {
    "points": {
      "type": "array",
      "items": { "type": "object", "required": ["id","x","y"],
        "properties": { "id":{"type":"string"}, "x":{"type":"number"}, "y":{"type":"number"} } }
    },
    "primitives": {
      "type": "array",
      "items": {
        "oneOf": [
          { "type":"object","required":["type","id","p1","p2"],
            "properties":{"type":{"const":"Line"},"id":{"type":"string"},"p1":{"type":"string"},"p2":{"type":"string"}} },
          { "type":"object","required":["type","id","center","radius"],
            "properties":{"type":{"const":"Circle"},"id":{"type":"string"},"center":{"type":"string"},"radius":{"type":"number"}} },
          { "type":"object","required":["type","id","circle","start","end"],
            "properties":{"type":{"const":"Arc"},"id":{"type":"string"},"circle":{"type":"string"},"start":{"type":"string"},"end":{"type":"string"},"measure_deg":{"type":"number"}} }
        ]
      }
    },
    "symbols": {
      "type": "array",
      "items": { "type":"object", "required":["id","type","targets"],
        "properties": {
          "id":{"type":"string"},
          "type":{"enum":["angle_arc","tick_bar","parallel","perpendicular","tangent_mark"]},
          "targets":{"type":"array","items":{"type":["string","array"]}}
        }}
    },
    "texts": {
      "type":"array",
      "items":{"type":"object","required":["id","string","anchor"],
        "properties":{"id":{"type":"string"},"string":{"type":"string"},"anchor":{"type":"string"}}}
    },
    "relations": {
      "type":"array",
      "items":{"type":"object","required":["type"],
        "properties":{
          "type":{"enum":["sym2geo","text2geo"]},
          "symbol_id":{"type":"string"},
          "target_ids":{"type":"array","items":{"type":"string"}},
          "text_id":{"type":"string"},
          "target_id":{"type":"string"}
        }}
    },
    "givens": {
      "type":"object",
      "properties":{
        "arcs":{"type":"object","additionalProperties":{"type":"number"}},
        "lengths":{"type":"object","additionalProperties":{"type":"number"}},
        "angles":{"type":"object","additionalProperties":{"type":"number"}},
        "parallel":{"type":"array","items":{"type":"array","items":{"type":"string"}}},
        "perpendicular":{"type":"array","items":{"type":"array","items":{"type":"string"}}},
        "tangent":{"type":"array","items":{"type":"object","properties":{"line":{"type":"string"},"at":{"type":"string"}}}}
      }
    },
    "ask": { "type":"string" },
    "gold": {
      "type":"object","required":["answer","reasoning_keys","error_tags"],
      "properties":{
        "answer":{"type":"object","required":["value","unit"],"properties":{"value":{"type":"number"},"unit":{"type":"string"},"tol":{"type":"number"}}},
        "reasoning_keys":{"type":"array","items":{"type":"string"}},
        "error_tags":{"type":"array","items":{"type":"string"}}
      }
    }
  }
}
```

### Example `items/T3/scene.yaml` (tangent–secant external angle)
```yaml
points:
  - {id: O, x: 200, y: 200}
  - {id: A, x: 300, y: 200}
  - {id: B, x: 120, y: 120}
  - {id: C, x: 260, y: 320}
  - {id: P, x: 340, y: 140}

primitives:
  - {type: Circle, id: circleO, center: O, radius: 120}
  - {type: Line, id: PA, p1: P, p2: A}
  - {type: Line, id: PCB, p1: P, p2: C}
  - {type: Arc, id: arcAB, circle: circleO, start: A, end: B, measure_deg: 110}
  - {type: Arc, id: arcCB, circle: circleO, start: C, end: B, measure_deg: 50}

symbols:
  - {id: tangA, type: tangent_mark, targets: [PA, A]}

texts:
  - {id: tAB, string: "110°", anchor: A}
  - {id: tCB, string: "50°",  anchor: C}

relations:
  - {type: sym2geo, symbol_id: tangA, target_ids: [PA, A]}
  - {type: text2geo, text_id: tAB, target_id: arcAB}
  - {type: text2geo, text_id: tCB, target_id: arcCB}

givens:
  arcs: { AB: 110, CB: 50 }
  tangent: [ {line: PA, at: A} ]

ask: "angle(APC)"

gold:
  answer: { value: 30, unit: "deg", tol: 0 }
  reasoning_keys:
    - "external-angle = 1/2 (far arc - near arc)"
    - "tangent defines intercepted arc via chord AB"
  error_tags: ["AC","TG"]
```

---

## Gold / Variants / Response Schemas

### `schema/gold.schema.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Gold",
  "type": "object",
  "required": ["answer","reasoning_keys","error_tags"],
  "properties": {
    "answer": {
      "type": "object",
      "required": ["value","unit"],
      "properties": { "value":{"type":"number"}, "unit":{"type":"string"}, "tol":{"type":"number"} }
    },
    "acceptable": { "type":"array", "items":{"type":"string"} },
    "reasoning_keys": { "type":"array", "items":{"type":"string"} },
    "error_tags": { "type":"array", "items":{"type":"string"} }
  }
}
```

### `schema/variants.schema.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Variants",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["variant_id"],
    "properties": {
      "variant_id": {"type":"string"},
      "text_included": {"type":"boolean"},
      "text_drop": { "type":"array", "items":{"type":"string"} },
      "image": {"type":["string","null"]},
      "render_ops": {"type":"array","items":{"type":"string"}},
      "mark_removed": {"type":"array","items":{"type":"string"}},
      "expected_effect": {"type":"string"},
      "decisive_symbol": {"type":"string"}
    }
  }
}
```

### `schema/response.schema.json` (model output)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Model Response",
  "type": "object",
  "required": ["final_answer","figure_facts_used","text_givens_used","assumptions"],
  "properties": {
    "final_answer": {"type":"string"},
    "figure_facts_used": {"type":"array","items":{"type":"string"}},
    "text_givens_used": {"type":"array","items":{"type":"string"}},
    "assumptions": {"type":"array","items":{"type":"string"}}
  }
}
```

---

## Rendering (implementation notes)

- **Language**: Python with `svgwrite` (or any SVG writer).  
- **Layers**: group elements into `<g id="primitives">`, `<g id="symbols">`, `<g id="labels">`.  
- **Glyphs**: keep tiny path templates for angle arcs, tick bars, ⟂ squares, ∥ chevrons, and a small tangency “⊥” marker.  
- **Export**: write `.svg` and rasterize to 96/144/300 DPI (e.g., with CairoSVG).  
- **ID discipline**: all elements must have stable IDs that match the scene graph entries.

### Skeleton (`tools/render_svg.py`)
```python
# Pseudocode sketch
def render(scene_yaml, svg_out, png_outs=[("96",96),("144",144),("300",300)]):
    scene = load_yaml(scene_yaml)

    svg = SVG(width=W, height=H)
    Gp, Gs, Gl = svg.group(id="primitives"), svg.group(id="symbols"), svg.group(id="labels")

    # draw primitives
    for prim in scene["primitives"]:
        if prim["type"] == "Circle": draw_circle(Gp, prim)
        elif prim["type"] == "Line": draw_line(Gp, prim)
        elif prim["type"] == "Arc":  draw_arc(Gp, prim)

    # draw symbols (angle_arc, tick_bar, parallel, perpendicular, tangent_mark)
    for sym in scene["symbols"]:
        draw_symbol(Gs, sym, scene)

    # draw labels
    for txt in scene["texts"]:
        draw_label(Gl, txt, scene)

    svg.save(svg_out)
    for tag, dpi in png_outs: rasterize(svg_out, f"{basename}_{tag}.png", dpi=dpi)
```

---

## Variant Generation

### `tools/make_variants.py` (core transforms)
```python
def toggle_parallel(scene, L1, L2, add=True): ...
def remove_symbol(scene, sym_id): ...
def nudge_label(scene, text_id, dx, dy): ...
def swap_labels(scene, t1, t2): ...
def rotate_canvas(scene, theta_deg): ...
def thin_symbols(scene, alpha=0.5): ...
def rasterize(svg_path, dpi): ...
```

**Invariants:**
- Label **anchor** stays attached to the geometry point; only the rendered label position changes.  
- Only **one** decisive symbol is removed in `mark_removed` variants.  
- Minor cosmetic edits (rotation, thin marks) do **not** change the gold answer.

**Unit tests:**
- `tests/test_flip_effect.py` asserts the gold answer flips or becomes “indeterminate” for decisive edits.  
- `tests/test_annotation_links.py` checks `sym2geo`/`text2geo` completeness.

---

## Example Item — T3 (external tangent–secant angle)

**Text (Full):**  
“In circle \(O\), line \(PA\) is tangent at \(A\). Secant \(PCB\) intersects the circle at \(C\) and \(B\). Minor arcs satisfy \(m\widehat{AB}=110^\circ\), \(m\widehat{CB}=50^\circ\). Find \(\angle APC\).”

**Gold:** \(30^\circ\).

**`items/T3/T3.gold.json`**
```json
{
  "id": "T3",
  "ask": "angle(APC)",
  "gold": {
    "answer": {"value": 30, "unit": "deg", "tol": 0},
    "acceptable": ["30","30°"],
    "reasoning_keys": [
      "external-angle = 1/2 (far arc - near arc)",
      "tangent defines intercepted arc via chord AB"
    ],
    "error_tags": ["AC","TG"]
  }
}
```

**`items/T3/T3.variants.json`**
```json
[
  {"variant_id":"T3_full_txtimg", "text_included":true, "image":"T3_144.png"},
  {"variant_id":"T3_img_only",     "text_included":false, "image":"T3_144.png"},
  {"variant_id":"T3_txt_only",     "text_included":true,  "image":null},
  {"variant_id":"T3_adversarial",  "image":"T3_rot10_96.png", "render_ops":["rotate10","thin_symbols","raster96"]},
  {"variant_id":"T3_mark_removed", "image":"T3_no_tangent_144.png", "mark_removed":["tangA"], "expected_effect":"flip_or_invalidate", "decisive_symbol":"tangA"}
]
```

**Prompt (with process contract)**
```
You must respond in this exact structure:

FINAL_ANSWER: <number + unit>

FIGURE_FACTS_USED:
- <only marks visible in the diagram, e.g., "OT ⟂ PA", "arc AB = 110° (near-arc label)">

TEXT_GIVENS_USED:
- <only given statements from the prompt; write "none" if none>

ASSUMPTIONS:
- none
```

---

## Evaluator (reference)

### Grounding P/R/F1
```python
def grounding_prf(used_facts, truth_facts):
    used = set(normalize(f) for f in used_facts)
    truth = set(normalize(f) for f in truth_facts)
    tp = len(used & truth); fp = len(used - truth); fn = len(truth - used)
    P = tp / (tp + fp) if (tp + fp) else 0.0
    R = tp / (tp + fn) if (tp + fn) else 0.0
    F1 = 2*P*R/(P+R) if (P+R) else 0.0
    return P, R, F1
```

### Auto‑flags
```python
def invented_parallel(used, truth):  # GP
    return any(("∥" in f or "parallel" in f) and f not in truth for f in used)

def tangent_missing(truth, used):    # TG
    # If tangent ⟂ radius is in truth but not cited among used
    needed = {f for f in truth if "⊥" in f or "tangent@" in f}
    return bool(needed) and not any(u in needed or "⊥" in u or "tangent" in u for u in used)

def arc_chord_conflict(truth, used): # AC
    # Claims arc measure when only chord length is labeled (or vice versa)
    arc_claim = any("arc " in u or "arc(" in u for u in used)
    chord_only = not any("arc" in t for t in truth) and any("chord" in t or "Line" in t for t in truth)
    return arc_claim and chord_only

def label_anchor_violation(used, truth): # LC
    # If used fact references label position rather than anchor link
    return any("label position" in u for u in used)

def mentions_visual_scale(pred):     # NS
    return "looks" in pred.explanation.lower() or "by scale" in pred.explanation.lower()
```

### Contrastive Consistency
```python
def contrastive_check(base_ans, edited_ans, policy="flip_or_invalidate"):
    if policy == "flip_or_invalidate":
        return base_ans != edited_ans or edited_ans in {"indeterminate","not determinable"}
    return True
```

---

## Definitions of Done (per step)

- **Step 1 (Data):** 20 base items; each has one decisive mark/label; unique answers.  
- **Step 2 (Schema):** `scene.schema.json` validated; sample `scene.yaml` passes.  
- **Step 3 (Renderer):** Re‑render is pixel‑identical; layers & IDs stable; 96/144/300 DPI exported.  
- **Step 4 (Variants):** Decisive edits change gold or mark item as indeterminate; unit tests pass.  
- **Step 5 (Gold/PGDP):** Every symbol linked; text labels anchored; validator scripts pass.  
- **Step 6 (Prompt):** Fixed contract enforced in the harness.  
- **Step 8 (Eval):** CSV with Accuracy, Grounding P/R/F1, Consistency, error codes.  
- **Step 9 (MVD):** 100 samples (20×5 variants) produced and evaluated.  
- **Step 12 (Report):** Tables/plots rendered; two case studies written.  
- **Step 13 (Release):** Dataset card + scripts published.

---

## Ethical & Licensing Notes

- Draw **original** figures. Do not copy textbook diagrams.  
- Avoid personally identifiable content.  
- License the dataset under a permissive data license (e.g., CC BY‑SA 4.0 or CC BY 4.0) and your code under MIT/Apache‑2.0.  
- Document intended use: *research on diagram‑grounded reasoning*, not classroom grading.

---

## Extensions (optional, future work)

- Add **program‑checkable** solvers for a subset (e.g., tangent–secant) to recompute answers after edits.  
- Expand to **3D projections**, **counting problems**, and **coordinate vs. picture contradiction** cases.  
- Provide a **web viewer** that overlays model‑claimed facts vs. ground truth (green/red).

---

## Glossary

- **Primitive:** geometric element: point, line, circle, arc.  
- **Symbol:** visual mark conveying a relation (tick, angle arc, ∥, ⟂, tangent mark).  
- **sym2geo / text2geo:** links from symbols/text to their intended primitives.  
- **Decisive mark:** a symbol whose presence/absence changes the correct answer.

---

## Appendix A — Example `prompt.txt`
```
Problem:
In circle O, line PA is tangent at A. Secant PCB intersects the circle at C and B. 
The minor arcs satisfy m(AB)=110°, m(CB)=50°. Find ∠APC.

Instructions:
- Do NOT assume figures are to scale.
- Use ONLY marks visible in the diagram unless explicitly stated in the text.
- Follow the output contract below exactly.

RESPONSE FORMAT (mandatory):
FINAL_ANSWER: <number + unit>

FIGURE_FACTS_USED:
- <...>

TEXT_GIVENS_USED:
- <...>

ASSUMPTIONS:
- none
```

---

## Appendix B — Minimal `validate_gold.py` checks
```python
def validate_links(pgdp):
    # Every symbol must have sym2geo relation; every text must have text2geo if it carries a measure.
    symbol_ids = {s["id"] for s in pgdp["symbols"]}
    linked_symbols = {r["symbol_id"] for r in pgdp["relations"] if r["type"]=="sym2geo"}
    assert symbol_ids <= linked_symbols, "Unlinked symbols exist"

def decisive_mark_present(item):
    # Ensure the 'decisive_symbol' referenced in variants exists in the base scene
    ids = {s["id"] for s in item["symbols"]}
    for v in item["variants"]:
        if "decisive_symbol" in v:
            assert v["decisive_symbol"] in ids
```

---

## Appendix C — Example symbol glyph specs (conceptual)
- **angle_arc:** small arc centered at vertex with fixed pixel radius.  
- **tick_bar:** short perpendicular segment at mid‑edge.  
- **perpendicular:** tiny square at intersection (8×8 px).  
- **parallel:** double chevrons on both lines.  
- **tangent_mark:** mini “⊥” placed at the point of tangency.

---

## Appendix D — Makefile targets (optional)
```makefile
render:
\tpython tools/render_svg.py

variants:
\tpython tools/make_variants.py

validate:
\tpython tools/validate_gold.py

eval:
\tpython eval/evaluate.py --items items/ --out results.csv
```

---

## Final Notes

Keep the dataset **small, sharp, and symbol‑aware**. The novelty here is not breadth but **diagnostic power**: if a model claims “AB ∥ CD” while no ∥ mark or text gives it, you can prove it and score it.

Good luck—and may your ⟂ squares always be read correctly.
