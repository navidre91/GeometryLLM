#!/usr/bin/env python3
"""
rommath_offline_demo.py

Builds a small *offline* geometry seed database (no internet) from `seeds/rommath_seed_examples.jsonl`.
Creates items/<ID>/ folders with prompt, gold, source, external URL, scene.yaml (stub), variants.json.
This is for wiring tests; for full data, run rommath_scraper_tailored.py against Hugging Face.

Usage:
  python scripts/rommath_offline_demo.py --out ./out_demo
"""
import argparse, json, os, re
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--append-prompt-contract", default="true", choices=["true","false"])
    args = ap.parse_args()

    base = Path(__file__).resolve().parents[1]
    seeds_path = base / "seeds" / "rommath_seed_examples.jsonl"
    rows = [json.loads(line) for line in seeds_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    PROMPT_CONTRACT = """
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
- none
"""

    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for row in rows:
        item_id = row["id"]
        d = out_dir / "items" / re.sub(r"[^a-zA-Z0-9._-]+","-", item_id)
        (d/"assets").mkdir(parents=True, exist_ok=True)

        prompt_text = row["question"]
        if args.append_prompt_contract == "true":
            prompt_text += PROMPT_CONTRACT
        (d/"prompt.txt").write_text(prompt_text, encoding="utf-8")

        gold = {
            "id": row["id"],
            "answer": row.get("answer"),
            "choices": row.get("choices"),
            "question_type": row.get("question_type"),
            "subset": row.get("subset"),
            "split": row.get("split")
        }
        (d/"gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")

        src = {
            "split_json_url": "(demo)",
            "image_relpath": "(demo)",
            "image_url": row.get("image_url"),
            "dataset": "yilun-org/RoMMath (reference URL only)"
        }
        (d/"source.json").write_text(json.dumps(src, ensure_ascii=False, indent=2), encoding="utf-8")
        (d/"external_image_url.txt").write_text((row.get("image_url") or "")+"\n", encoding="utf-8")

        # No internet: we can't download the image. Keep URL.
        # scene stub
        scene = {
            "version":"0.1",
            "id": row["id"],
            "renderer":{"type":"external-raster","uri": row.get("image_url")},
            "primitives":[],
            "symbols":[],
            "relations":[],
            "metadata": {
                "subset": row.get("subset"),
                "split": row.get("split"),
                "question_type": row.get("question_type"),
                "diagnostic_hint": row.get("diagnostic_hint")
            }
        }
        (d/"scene.yaml").write_text(json.dumps(scene, indent=2), encoding="utf-8")

        variants = [
            {"variant_id": f"{item_id}_full_txtimg", "text_included": True,  "image": "assets/figure.png"},
            {"variant_id": f"{item_id}_img_only",    "text_included": False, "image": "assets/figure.png"},
            {"variant_id": f"{item_id}_txt_only",    "text_included": True,  "image": None}
        ]
        (d/"variants.json").write_text(json.dumps(variants, indent=2), encoding="utf-8")

        manifest.append({"id": item_id, "dir": str(d), "subset": row.get("subset"), "split": row.get("split")})

    (out_dir/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Demo built with {len(manifest)} items at {out_dir}")

if __name__ == "__main__":
    main()
