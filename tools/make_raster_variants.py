#!/usr/bin/env python3
"""Utility for adversarial edits to raster-only geometry items.

The RoMMath "origin" items ship with pre-rendered PNGs and empty scene graphs.
This script automates simple pixel-space edits (erase, blur, copy/paste, draw
lines, add text) and keeps ``variants.json`` in sync with the newly created
assets.  Supply a YAML or JSON config describing each variant you want to add.

Example configuration (see ``configs/raster_variants.sample.yaml``)::

    items:
      - id: geo697-origin
        base_image: assets/figure.png
        output_image: assets/figure_no_arc.png
        variant:
          variant_id: geo697-origin_mark_removed
          text_included: true
          image: assets/figure_no_arc.png
          expected_effect: flip_or_invalidate
          decisive_symbol: arc_label_110
        operations:
          - type: erase_rect
            bbox: [405, 165, 470, 225]
            color: [255, 255, 255, 255]

Run with::

    python tools/make_raster_variants.py \
        --config configs/raster_variants.sample.yaml \
        --items-root out_rommath_origin/items

Operations supported:
    * ``erase_rect``  – fill an axis-aligned rectangle.
    * ``draw_line``   – draw a straight line between two points.
    * ``add_text``    – overlay text (uses default PIL font unless ``font_path`` provided).
    * ``copy_paste``  – copy a rectangular patch elsewhere.
    * ``blur_rect``   – blur a rectangular patch with Gaussian blur.
    * ``rotate``      – rotate the entire image by a given angle.

The script will refuse to overwrite existing images/variants unless
``--overwrite`` is passed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

Operation = Dict[str, Any]


def load_config(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "items" not in data:
        raise ValueError("Config must be a mapping with an 'items' key")
    if not isinstance(data["items"], Iterable):
        raise ValueError("'items' must be a list")
    return data


def ensure_variant_entry(variants: List[Dict[str, Any]], variant: Dict[str, Any], overwrite: bool) -> List[Dict[str, Any]]:
    vid = variant.get("variant_id")
    if not vid:
        raise ValueError("variant entry must include 'variant_id'")
    idx = next((i for i, entry in enumerate(variants) if entry.get("variant_id") == vid), None)
    if idx is None:
        variants.append(variant)
    else:
        if not overwrite:
            raise ValueError(f"variant_id '{vid}' already exists; pass --overwrite to replace it")
        variants[idx] = variant
    return variants


def resolve_base_image(item_dir: Path, suggested: str | None) -> Path:
    if suggested:
        candidate = item_dir / suggested
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"base_image '{suggested}' not found under {item_dir}")

    variants_path = item_dir / "variants.json"
    variants = json.loads(variants_path.read_text(encoding="utf-8"))
    for entry in variants:
        image_rel = entry.get("image")
        if image_rel:
            candidate = item_dir / image_rel
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"Could not infer base image for {item_dir}")


def color_tuple(values: Iterable[int] | None, default: Tuple[int, int, int, int] = (255, 255, 255, 255)) -> Tuple[int, int, int, int]:
    if values is None:
        return default
    vals = list(values)
    if len(vals) not in (3, 4):
        raise ValueError("color must have 3 (RGB) or 4 (RGBA) integers")
    if len(vals) == 3:
        vals.append(255)
    return tuple(int(v) for v in vals)


def _resolve_resample(name: str | None) -> int:
    if not name:
        return Image.BICUBIC
    key = name.upper()
    return getattr(Image, key, Image.BICUBIC)


def apply_operation(image: Image.Image, op: Operation) -> Image.Image:
    op_type = op.get("type")
    if not op_type:
        raise ValueError(f"Operation missing 'type': {op}")
    draw = ImageDraw.Draw(image, "RGBA")

    if op_type == "erase_rect":
        bbox = op.get("bbox")
        if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
            raise ValueError("erase_rect requires bbox=[x1,y1,x2,y2]")
        draw.rectangle(bbox, fill=color_tuple(op.get("color")))
        return image

    elif op_type == "draw_line":
        points = op.get("points")
        if not (isinstance(points, (list, tuple)) and len(points) >= 4):
            raise ValueError("draw_line requires points=[x1,y1,x2,y2,...]")
        width = int(op.get("width", 3))
        draw.line(points, fill=color_tuple(op.get("color"), default=(0, 0, 0, 255)), width=width)
        return image

    elif op_type == "add_text":
        text = op.get("text", "")
        position = op.get("position")
        if not (isinstance(position, (list, tuple)) and len(position) == 2):
            raise ValueError("add_text requires position=[x,y]")
        font_size = int(op.get("font_size", 16))
        font_path = op.get("font_path")
        if font_path:
            font = ImageFont.truetype(str(Path(font_path)), font_size)
        else:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except IOError:
                font = ImageFont.load_default()
        draw.text(position, text, fill=color_tuple(op.get("fill"), default=(0, 0, 0, 255)), font=font)
        return image

    elif op_type == "copy_paste":
        src_bbox = op.get("src_bbox")
        dst_xy = op.get("dst_xy")
        if not (isinstance(src_bbox, (list, tuple)) and len(src_bbox) == 4):
            raise ValueError("copy_paste requires src_bbox=[x1,y1,x2,y2]")
        if not (isinstance(dst_xy, (list, tuple)) and len(dst_xy) == 2):
            raise ValueError("copy_paste requires dst_xy=[x,y]")
        patch = image.crop(tuple(src_bbox))
        image.paste(patch, tuple(int(v) for v in dst_xy))
        if op.get("clear_src"):
            draw.rectangle(src_bbox, fill=color_tuple(op.get("clear_color")))
        return image

    elif op_type == "blur_rect":
        bbox = op.get("bbox")
        if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
            raise ValueError("blur_rect requires bbox=[x1,y1,x2,y2]")
        radius = float(op.get("radius", 3.0))
        rect = image.crop(tuple(bbox))
        rect = rect.filter(ImageFilter.GaussianBlur(radius=radius))
        image.paste(rect, tuple(bbox[:2]))
        return image

    elif op_type == "rotate":
        angle = float(op.get("angle", 0.0))
        expand = bool(op.get("expand", True))
        fill = color_tuple(op.get("fill"), default=(255, 255, 255, 0))
        resample = _resolve_resample(op.get("resample"))
        rotated = image.rotate(angle, expand=expand, resample=resample, fillcolor=fill)
        if op.get("keep_size") and rotated.size != image.size:
            target_w, target_h = image.size
            rw, rh = rotated.size
            if rw >= target_w and rh >= target_h:
                left = max(0, (rw - target_w) // 2)
                top = max(0, (rh - target_h) // 2)
                cropped = rotated.crop((left, top, left + target_w, top + target_h))
                return cropped
            canvas = Image.new(image.mode, (target_w, target_h), fill)
            left = max(0, (target_w - rw) // 2)
            top = max(0, (target_h - rh) // 2)
            canvas.paste(rotated, (left, top))
            return canvas
        return rotated

    else:
        raise ValueError(f"Unsupported operation type '{op_type}'")

    return image


def process_item(item_cfg: Dict[str, Any], items_root: Path, overwrite: bool, dry_run: bool = False) -> None:
    item_id = item_cfg.get("id")
    if not item_id:
        raise ValueError("Each config entry must include an 'id'")
    item_dir = items_root / item_id
    if not item_dir.exists():
        raise FileNotFoundError(f"Item directory not found: {item_dir}")

    base_image_path = resolve_base_image(item_dir, item_cfg.get("base_image"))
    output_rel = item_cfg.get("output_image")
    if not output_rel:
        raise ValueError(f"Entry {item_id} missing 'output_image'")
    output_path = item_dir / output_rel

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Output image already exists: {output_path}. Pass --overwrite to replace it.")

    operations = item_cfg.get("operations", [])
    if not isinstance(operations, list):
        raise ValueError("'operations' must be a list")

    print(f"[raster-variants] Editing {item_id}: {base_image_path} -> {output_path}")
    if dry_run:
        return

    image = Image.open(base_image_path).convert("RGBA")
    for op in operations:
        image = apply_operation(image, op)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)

    variant_entry = item_cfg.get("variant")
    if not isinstance(variant_entry, dict):
        raise ValueError(f"Entry {item_id} must provide a 'variant' mapping")

    variants_path = item_dir / "variants.json"
    variants = json.loads(variants_path.read_text(encoding="utf-8"))
    ensure_variant_entry(variants, variant_entry, overwrite)
    variants_path.write_text(json.dumps(variants, indent=2) + "\n", encoding="utf-8")

    if "diagnostic_note" in item_cfg:
        diag_path = item_dir / "diagnostic.json"
        try:
            diagnostic = json.loads(diag_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            diagnostic = {}
        notes = diagnostic.setdefault("notes", [])
        if item_cfg["diagnostic_note"] not in notes:
            notes.append(item_cfg["diagnostic_note"])
        diag_path.write_text(json.dumps(diagnostic, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create adversarial raster variants for RoMMath items")
    parser.add_argument("--config", required=True, help="YAML/JSON config describing edits")
    parser.add_argument("--items-root", default="out_rommath_origin/items", help="Root directory containing item folders")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing existing images/variants")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files")
    args = parser.parse_args()

    config_path = Path(args.config)
    items_root = Path(args.items_root)
    data = load_config(config_path)

    for entry in data.get("items", []):
        process_item(entry, items_root, overwrite=args.overwrite, dry_run=args.dry_run)

    print("[raster-variants] Done.")


if __name__ == "__main__":
    main()
