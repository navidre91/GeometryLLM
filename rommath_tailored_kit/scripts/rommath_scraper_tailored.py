#!/usr/bin/env python3
"""
rommath_scraper_tailored.py

Origin-only, geometry-only (default: id-prefix 'geo') scraper/ingester for RoMMath.
- Downloads split JSON from Hugging Face (validation/test).
- Filters to subset 'origin' by default.
- Assigns a diagnostic category using keyword heuristics that target your five failure modes.
- Writes items/<ID>/ with prompt, gold, image (PNG), scene stub, variants, and diagnostic.json.

Usage:
  pip install httpx tqdm
  python scripts/rommath_scraper_tailored.py \
      --split validation \
      --subset origin \
      --id-prefix geo \
      --limit 50 \
      --out ./out_rommath_origin \
      --diagnostic-only true \
      --append-prompt-contract true
"""
import argparse, os, json, re, sys
from pathlib import Path
import httpx
from tqdm import tqdm

RAW_BASE = "https://huggingface.co/datasets/yilun-org/RoMMath/raw/main/"
RESOLVE_BASE = "https://huggingface.co/datasets/yilun-org/RoMMath/resolve/main/"
SPLIT_FILE = {"validation": "validation.json", "test": "test.json"}

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

def fetch_split_json(split: str, client: httpx.Client):
    url = RAW_BASE + SPLIT_FILE[split]
    r = client.get(url, timeout=60)
    r.raise_for_status()
    return r.json()

def build_item_dir(base_out: Path, item_id: str) -> Path:
    d = base_out / "items" / re.sub(r"[^a-zA-Z0-9._-]+","-", item_id)
    (d / "assets").mkdir(parents=True, exist_ok=True)
    return d

def resolve_image_url(row):
    # RoMMath rows contain ./RoMMath/image/<file>.png in 'image'
    rel = row.get("image","").replace("./RoMMath/","")
    return RESOLVE_BASE + rel

def diagnostic_map(text: str):
    # Very simple keyword heuristics per category
    t = (text or "").lower()
    scores = {
        "tangent-secant": 0,
        "arc-vs-chord": 0,
        "invented-parallel-perp": 0,
        "label-anchoring": 0,
        "not-to-scale-vs-marked": 0
    }
    if any(k in t for k in ["tangent", "secant", "point of tangency", "tangent-chord"]):
        scores["tangent-secant"] += 2
    if any(k in t for k in ["arc", "chord", "inscribed angle", "central angle", "intercepted arc"]):
        scores["arc-vs-chord"] += 2
    if any(k in t for k in ["parallel", "perpendicular", "∥", "⟂", "similar triangles", "similarity"]):
        scores["invented-parallel-perp"] += 2
    if any(k in t for k in ["midpoint", "foot of perpendicular", "bisect", "label", "marked", "tick"]):
        scores["label-anchoring"] += 1
    if any(k in t for k in ["isosceles", "equilateral", "ab = ac", "equal sides", "not to scale"]):
        scores["not-to-scale-vs-marked"] += 1
    # Pick top-scoring category (ties -> arbitrary stable order)
    cat = None
    best = 0
    for k,v in scores.items():
        if v > best:
            best = v
            cat = k
    return {"category": cat, "scores": scores}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="validation", choices=["validation","test"])
    ap.add_argument("--subset", default="origin", help="origin by default; you may pass multiple by comma")
    ap.add_argument("--id-prefix", default="geo")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--out", required=True)
    ap.add_argument("--diagnostic-only", default="true", choices=["true","false"])
    ap.add_argument("--append-prompt-contract", default="true", choices=["true","false"])
    args = ap.parse_args()

    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    subset_whitelist = [s.strip() for s in args.subset.split(",") if s.strip()]

    headers = {}
    token = os.environ.get("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        rows = fetch_split_json(args.split, client)
        picked = []
        for row in rows:
            rid = row.get("id","")
            subset = row.get("subset","")
            if not rid.startswith(args.id_prefix): 
                continue
            if subset_whitelist and subset not in subset_whitelist:
                continue
            picked.append(row)
            if args.limit>0 and len(picked)>=args.limit:
                break

        manifest = []
        for row in tqdm(picked, desc="Importing"):
            item_id = row["id"]
            d = build_item_dir(out_dir, item_id)

            qtext = (row.get("question") or "").strip()
            if args.append_prompt_contract == "true":
                qtext = qtext + PROMPT_CONTRACT

            # prompt
            (d/"prompt.txt").write_text(qtext, encoding="utf-8")

            # gold (raw; keep as-is)
            gold = {
                "id": item_id,
                "answer": row.get("answer"),
                "choices": row.get("choices") or None,
                "question_type": row.get("question_type"),
                "subset": row.get("subset"),
                "split": args.split,
            }
            (d/"gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")

            # source + image url
            img_url = resolve_image_url(row)
            source = {
                "split_json_url": RAW_BASE + (SPLIT_FILE[args.split]),
                "image_relpath": row.get("image"),
                "image_url": img_url,
                "dataset": "yilun-org/RoMMath"
            }
            (d/"source.json").write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
            (d/"external_image_url.txt").write_text(img_url+"\n", encoding="utf-8")

            # download image
            try:
                r = client.get(img_url, timeout=60)
                r.raise_for_status()
                (d/"assets").mkdir(exist_ok=True, parents=True)
                (d/"assets"/"figure.png").write_bytes(r.content)
            except Exception as e:
                (d/"download_error.txt").write_text(str(e), encoding="utf-8")

            # diagnostic mapping
            diag = diagnostic_map(row.get("question","") or "")
            (d/"diagnostic.json").write_text(json.dumps(diag, indent=2), encoding="utf-8")

            # optional filter: keep only mapped
            if args.diagnostic_only == "true" and not diag.get("category"):
                # Remove directory if created
                for root, dirs, files in os.walk(d, topdown=False):
                    for name in files: os.remove(os.path.join(root, name))
                    for name in dirs: os.rmdir(os.path.join(root, name))
                try: os.rmdir(d)
                except OSError: pass
                continue

            # scene stub (raster reference; you will replace with vector later)
            scene_stub = {
                "version": "0.1",
                "id": item_id,
                "renderer": {"type":"external-raster","uri": img_url},
                "primitives": [],
                "symbols": [],
                "relations": [],
                "metadata": {
                    "subset": row.get("subset"),
                    "split": args.split,
                    "question_type": row.get("question_type"),
                    "diagnostic_category": diag.get("category"),
                    "diagnostic_scores": diag.get("scores")
                }
            }
            (d/"scene.yaml").write_text(json.dumps(scene_stub, indent=2), encoding="utf-8")

            # minimal variants for modality ablation
            variants = [
                {"variant_id": f"{item_id}_full_txtimg", "text_included": True,  "image": "assets/figure.png"},
                {"variant_id": f"{item_id}_img_only",    "text_included": False, "image": "assets/figure.png"},
                {"variant_id": f"{item_id}_txt_only",    "text_included": True,  "image": None}
            ]
            (d/"variants.json").write_text(json.dumps(variants, indent=2), encoding="utf-8")

            manifest.append({
                "id": item_id,
                "dir": str(d),
                "subset": row.get("subset"),
                "split": args.split,
                "diagnostic_category": diag.get("category")
            })

        (out_dir/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Imported {len(manifest)} items to {out_dir}")

if __name__ == "__main__":
    main()
