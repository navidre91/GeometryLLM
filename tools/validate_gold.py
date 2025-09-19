#!/usr/bin/env python3
r"""Grounding validator for geometry benchmark assets.

Checks performed:

* ``scene.yaml`` (if present) validates against ``schema/scene.schema.json``.
* Every symbol defined in the scene has a corresponding ``sym2geo`` relation.
* Any text string that resembles a measurement (matches ``\d+°`` or
  ``=\s*\d+``) has a ``text2geo`` relation.
* Variants declaring ``expected_effect: "flip_or_invalidate"`` reference a
  decisive symbol that exists in the base scene (symbol or text ID).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

try:
    import jsonschema
except Exception:  # pragma: no cover - optional dependency
    jsonschema = None


MEASURE_PATTERN = re.compile(r"(\d+\s*°|=\s*\d+)")


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def validate_scene(scene_path: Path, schema_path: Path):
    scene = load_yaml(scene_path)

    if schema_path.exists() and jsonschema:
        schema = load_json(schema_path)
        jsonschema.validate(scene, schema)

    relations = scene.get("relations", [])
    sym_ids = {sym["id"] for sym in scene.get("symbols", [])}
    linked_symbols = {rel["symbol_id"] for rel in relations if rel.get("type") == "sym2geo"}
    missing_symbols = sym_ids - linked_symbols
    if missing_symbols:
        raise AssertionError(f"Unlinked symbols in {scene_path}: {sorted(missing_symbols)}")

    texts = scene.get("texts", [])
    measure_text_ids = {
        text["id"]
        for text in texts
        if MEASURE_PATTERN.search(text.get("string", ""))
    }
    linked_texts = {rel["text_id"] for rel in relations if rel.get("type") == "text2geo"}
    missing_measures = measure_text_ids - linked_texts
    if missing_measures:
        raise AssertionError(f"Unlinked measure texts in {scene_path}: {sorted(missing_measures)}")


def validate_variants(scene_path: Path, variants_path: Path):
    scene = load_yaml(scene_path)
    variants = load_json(variants_path)

    symbol_ids = {sym["id"] for sym in scene.get("symbols", [])}
    text_ids = {text["id"] for text in scene.get("texts", [])}

    for variant in variants:
        if variant.get("expected_effect") == "flip_or_invalidate":
            decisive = variant.get("decisive_symbol")
            if not decisive:
                raise AssertionError(
                    f"Variant {variant.get('variant_id')} is missing decisive_symbol despite flip_or_invalidate"
                )
            if decisive not in symbol_ids and decisive not in text_ids:
                raise AssertionError(
                    f"Variant {variant.get('variant_id')} references decisive_symbol '{decisive}'"
                    f" not present in base scene {scene_path}"
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items_dir", default="items")
    parser.add_argument("--schema_dir", default="schema")
    args = parser.parse_args()

    items_dir = Path(args.items_dir)
    schema_dir = Path(args.schema_dir)
    schema_path = schema_dir / "scene.schema.json"

    for item_dir in sorted(p for p in items_dir.iterdir() if p.is_dir()):
        scene_path = item_dir / "scene.yaml"
        variants_path = item_dir / f"{item_dir.name}.variants.json"

        if scene_path.exists():
            print(f"[validate] {scene_path}")
            validate_scene(scene_path, schema_path)

        if variants_path.exists():
            validate_variants(scene_path, variants_path)

    print("[validate] OK")


if __name__ == "__main__":
    main()
