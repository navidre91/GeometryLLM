#!/usr/bin/env python3
"""
Sanity checks for items:
- scene.yaml validates against schema
- every symbol/text with measures is linked via relations
- decisive_symbol in variants exists in base scene
"""
import os, sys, json, argparse
from pathlib import Path

import yaml
try:
    import jsonschema
except Exception as e:
    jsonschema = None

def load_json(p): return json.load(open(p,'r',encoding='utf-8'))
def load_yaml(p): return yaml.safe_load(open(p,'r',encoding='utf-8'))

def validate_scene(scene_path, schema_path):
    scene = load_yaml(scene_path)
    if schema_path.exists() and jsonschema:
        try:
            jsonschema.validate(scene, load_json(schema_path))
        except Exception as e:
            raise AssertionError(f"Schema validation failed for {scene_path}: {e}")
    sym_ids = {s["id"] for s in scene.get("symbols",[])}
    linked_syms = {r["symbol_id"] for r in scene.get("relations",[]) if r.get("type")=="sym2geo"}
    missing = sym_ids - linked_syms
    if missing:
        raise AssertionError(f"Unlinked symbols in {scene_path}: {missing}")
    deg_texts = {t["id"] for t in scene.get("texts",[]) if "°" in t.get("string","")}
    linked_txts = {r["text_id"] for r in scene.get("relations",[]) if r.get("type")=="text2geo"}
    missing_t = deg_texts - linked_txts
    if missing_t:
        raise AssertionError(f"Unlinked measure texts in {scene_path}: {missing_t}")
    return True

def validate_variants(scene_path, variants_path):
    scene = load_yaml(scene_path)
    vlist = load_json(variants_path)
    sym_ids = {s["id"] for s in scene.get("symbols",[])}
    txt_ids = {t["id"] for t in scene.get("texts",[])}
    for v in vlist:
        dec = v.get("decisive_symbol")
        if dec and (dec not in sym_ids) and (dec not in txt_ids):
            raise AssertionError(f"decisive_symbol {dec} not found in base scene {scene_path}")
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items_dir", default="items")
    ap.add_argument("--schema_dir", default="schema")
    args = ap.parse_args()

    items_dir = Path(args.items_dir)
    schema_dir = Path(args.schema_dir)
    for item_dir in items_dir.iterdir():
        if not item_dir.is_dir(): continue
        scene = item_dir / "scene.yaml"
        variants = item_dir / f"{item_dir.name}.variants.json"
        if scene.exists():
            print(f"[validate] {scene}")
            validate_scene(scene, schema_dir/"scene.schema.json")
        if variants.exists():
            validate_variants(scene, variants)
    print("[validate] OK")
if __name__ == "__main__":
    main()
