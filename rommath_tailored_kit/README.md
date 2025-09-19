# RoMMath Geometry Seed Kit — Tailored (origin-only + diagnostic mapping)

This kit lets you import **geometry-only** items from the NAACL 2025 **RoMMath** dataset
and auto-map them to your five diagnostic categories:
1) Tangent–secant
2) Arc vs chord vs central/inscribed
3) Invented ∥/⟂ (similarity traps)
4) Label anchoring (midpoint/leader lines)
5) Not-to-scale vs marked equality

It ships with:
- `scripts/rommath_scraper_tailored.py` — a scraper/ingester that pulls from Hugging Face
  `yilun-org/RoMMath` and *defaults to* `--subset origin` (non‑adversarial) and `--id-prefix geo` (geometry).
  It materializes **`items/<ID>/`** folders containing `prompt.txt`, `gold.json`, `source.json`,
  `external_image_url.txt`, `assets/figure.png` (downloaded), `scene.yaml` (stub),
  `variants.json` (Full / IMG‑only / TXT‑only) and a `diagnostic.json` file with category mapping.
- `scripts/rommath_offline_demo.py` — no-internet generator that uses tiny paraphrased examples
  to build a **demo seed database** (so you can test wiring immediately).
- `seeds/rommath_seed_examples.jsonl` — 6 geometry examples (short paraphrases + metadata).
- `schemas/seed.schema.json` — schema for the demo seed rows.

> **Licensing & attribution**
> - Do *not* redistribute large portions of RoMMath text/images in your repo.
> - Use this kit to *reproduce* seeds from the official dataset on your own machine, following its license.
> - Cite the NAACL 2025 RoMMath paper and the dataset on Hugging Face.
> - The included examples are short paraphrases for local testing.

## Quickstart (online ingestion)

```bash
python -m venv .venv && source .venv/bin/activate
pip install httpx tqdm

# Import 50 geometry origin items into ./out_rommath_origin
python scripts/rommath_scraper_tailored.py   --split validation   --subset origin   --id-prefix geo   --limit 50   --out ./out_rommath_origin   --diagnostic-only true   --append-prompt-contract true
```

**Output structure (per item):**
```
out_rommath_origin/items/<ID>/
  prompt.txt
  gold.json                 # raw answer/choices as in RoMMath
  source.json               # dataset URLs + attribution
  external_image_url.txt    # absolute figure URL (HF resolve)
  assets/figure.png         # downloaded image
  scene.yaml                # stub that points to raster (replace later with vector scene)
  variants.json             # Full / IMG-only / TXT-only
  diagnostic.json           # category mapping + scores
```

## Offline demo (works without internet)

```bash
python scripts/rommath_offline_demo.py --out ./out_demo
```

This repository already includes a pre-built demo at: `/mnt/data/rommath_tailored_kit/out_origin_geometry_demo`

