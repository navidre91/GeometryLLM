#!/usr/bin/env python3
"""Variant generator for symbol-grounded geometry scenes.

Each entry in ``render_ops`` (within ``*.variants.json``) describes a small edit
to the base ``scene.yaml``. Supported operations:

``toggle_parallel:L1,L2:add`` / ``…:remove``
    Add or remove a ``parallel`` symbol between the two line primitives. When
    added, a matching ``sym2geo`` relation is also inserted. The generated
    symbol ID is deterministic (``par_<sorted-lines>``).

``toggle_perpendicular:L1,L2:add`` / ``…:remove``
    Add or remove a ``perpendicular`` symbol between the two line primitives.
    Symbol IDs are emitted as ``perp_<sorted-lines>``.

``remove_symbol:<id>``
    Remove the specified symbol or text label along with any linked relations.

``nudge:<text_id>:dx,dy``
    Adjust a text label’s ``offset`` (in pixels); renderer reads the offset when
    positioning the text.

``swap:<text_id1>,<text_id2>``
    Swap the rendered strings for two text labels in-place.

``rotate<deg>`` / ``thin_symbols``
    Metadata hooks preserved for backwards compatibility. They currently act as
    no-ops for rendering but remain in the output dictionary for future use.

Example usage::

    python tools/make_variants.py \
        --scene items/T1/scene.yaml \
        --variants items/T1/T1.variants.json \
        --out_dir items/T1
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import yaml


def load_json(path: str | Path):
    return json.load(open(Path(path), "r", encoding="utf-8"))


def load_yaml(path: str | Path):
    return yaml.safe_load(open(Path(path), "r", encoding="utf-8"))


def save_yaml(obj, path: str | Path) -> None:
    yaml.safe_dump(obj, open(Path(path), "w", encoding="utf-8"), sort_keys=False, allow_unicode=True)


def remove_symbol_or_text(scene: Dict, sid: str) -> Dict:
    scene["symbols"] = [s for s in scene.get("symbols", []) if s.get("id") != sid]
    scene["texts"] = [t for t in scene.get("texts", []) if t.get("id") != sid]
    scene["relations"] = [
        r
        for r in scene.get("relations", [])
        if not (
            (r.get("type") == "sym2geo" and r.get("symbol_id") == sid)
            or (r.get("type") == "text2geo" and r.get("text_id") == sid)
        )
    ]
    return scene


def remove_symbol(scene: Dict, sid: str) -> Dict:
    scene["symbols"] = [s for s in scene.get("symbols", []) if s.get("id") != sid]
    scene["relations"] = [
        r
        for r in scene.get("relations", [])
        if not (r.get("type") == "sym2geo" and r.get("symbol_id") == sid)
    ]
    return scene


SYMBOL_PREFIX = {
    "parallel": "par",
    "perpendicular": "perp",
}


def _canonical_symbol_id(sym_type: str, targets: List[str]) -> str:
    key = "_".join(sorted(set(targets)))
    prefix = SYMBOL_PREFIX.get(sym_type, sym_type)
    return f"{prefix}_{key}"


def toggle_symbol(scene: Dict, sym_type: str, line_ids: List[str], action: str) -> Dict:
    if len(line_ids) < 2:
        raise ValueError(f"toggle_{sym_type} requires at least two line IDs")

    sym_id = _canonical_symbol_id(sym_type, line_ids)

    if action == "add":
        if not any(s.get("id") == sym_id for s in scene.get("symbols", [])):
            symbol = {"id": sym_id, "type": sym_type, "targets": line_ids}
            scene.setdefault("symbols", []).append(symbol)
            relation = {
                "type": "sym2geo",
                "symbol_id": sym_id,
                "target_ids": line_ids,
            }
            scene.setdefault("relations", []).append(relation)
    elif action == "remove":
        scene = remove_symbol(scene, sym_id)
    else:
        raise ValueError(f"Unsupported action '{action}' for toggle_{sym_type}")

    return scene


def nudge_label(scene: Dict, text_id: str, dx: float, dy: float) -> Dict:
    for t in scene.get("texts", []):
        if t.get("id") == text_id:
            offset = t.get("offset", [0, 0])
            if len(offset) < 2:
                offset = [0, 0]
            t["offset"] = [offset[0] + dx, offset[1] + dy]
    return scene


def swap_labels(scene: Dict, t1: str, t2: str) -> Dict:
    texts = scene.get("texts", [])
    a = next((x for x in texts if x.get("id") == t1), None)
    b = next((x for x in texts if x.get("id") == t2), None)
    if a and b:
        a["string"], b["string"] = b["string"], a["string"]
    return scene


def apply_ops(scene: Dict, ops: List[str]):
    params = {"rotate": 0.0, "symbol_opacity": 1.0}
    if not ops:
        return scene, params

    for op in ops:
        if op.startswith("rotate"):
            match = re.match(r"rotate(-?\d+)", op)
            if match:
                params["rotate"] = float(match.group(1))
        elif op == "thin_symbols":
            params["symbol_opacity"] = 0.5
        elif op.startswith("remove_symbol:"):
            sid = op.split(":", 1)[1]
            scene = remove_symbol_or_text(scene, sid)
        elif op.startswith("nudge:"):
            _, body = op.split(":", 1)
            text_id, delta = body.split(":")
            dx, dy = delta.split(",")
            scene = nudge_label(scene, text_id, float(dx), float(dy))
        elif op.startswith("swap:"):
            _, pair = op.split(":", 1)
            t1, t2 = pair.split(",")
            scene = swap_labels(scene, t1, t2)
        elif op.startswith("toggle_parallel:"):
            _, body = op.split(":", 1)
            line_part, action = body.split(":")
            lines = [token.strip() for token in line_part.split(",") if token.strip()]
            scene = toggle_symbol(scene, "parallel", lines, action)
        elif op.startswith("toggle_perpendicular:"):
            _, body = op.split(":", 1)
            line_part, action = body.split(":")
            lines = [token.strip() for token in line_part.split(",") if token.strip()]
            scene = toggle_symbol(scene, "perpendicular", lines, action)
        else:
            raise ValueError(f"Unsupported render op: {op}")

    return scene, params


def call_renderer(scene_path: Path, out_dir: Path, rotate: float, symbol_opacity: float) -> None:
    root = Path(__file__).resolve().parents[1]
    render = root / "tools" / "render_svg.py"
    cmd = [
        sys.executable,
        str(render),
        "--scene",
        str(scene_path),
        "--out_dir",
        str(out_dir),
        "--rotate",
        str(rotate),
        "--symbol_opacity",
        str(symbol_opacity),
    ]
    subprocess.check_call(cmd, cwd=str(root))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True)
    parser.add_argument("--variants", required=True)
    parser.add_argument("--out_dir", required=True)
    args = parser.parse_args()

    scene_path = Path(args.scene)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_scene = load_yaml(scene_path)
    variants = load_json(args.variants)

    for variant in variants:
        scene = copy.deepcopy(base_scene)
        for sid in variant.get("mark_removed", []):
            scene = remove_symbol_or_text(scene, sid)

        scene, params = apply_ops(scene, variant.get("render_ops", []))

        tmp_scene = out_dir / f"{scene_path.stem}.{variant['variant_id']}.tmp.yaml"
        save_yaml(scene, tmp_scene)

        # Render and rename artefacts when requested.
        call_renderer(tmp_scene, out_dir, params["rotate"], params["symbol_opacity"])

        if variant.get("image"):
            base_svg = out_dir / f"{scene_path.stem}.svg"
            dst_svg = out_dir / variant["image"]
            if base_svg.exists():
                base_svg.replace(dst_svg)

        try:
            tmp_scene.unlink()
        except OSError:
            pass

        # Params retained for forward-compatibility.
        _ = params

    print("[make_variants] Done.")


if __name__ == "__main__":
    main()
