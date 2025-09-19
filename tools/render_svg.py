# tools/render_svg.py
"""Deterministic renderer for symbol-grounded geometry scenes.

This script consumes a scene YAML that conforms to ``schema/scene.schema.json``
and produces:
    * Layered SVG with stable group/element IDs.
    * Optional PNG rasters at multiple DPIs (best-effort).
    * PGDP-style JSON annotations mirroring the scene graph.

The implementation is intentionally lean; it only draws the primitive/symbol
types required by the benchmark spec. Additional glyphs can be layered in later
without touching the existing IDs so long as the helper functions preserve the
ordering guarantees below.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import yaml
from jsonschema import validate

import svgwrite

CANVAS_SIZE = 400  # square canvas, consistent across items for stability
STYLE_BLOCK = (
    ".prim { fill: none; stroke: black; stroke-width: 2; }\n"
    ".sym { fill: none; stroke: black; stroke-width: 2; }\n"
    ".lbl { font-family: Arial, sans-serif; font-size: 14px; }\n"
    ".measure { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; }\n"
    ".pt { fill: black; }\n"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_scene(path: Path, schema_path: Path | None = None) -> Dict:
    """Parse a YAML scene file and validate it against the JSON schema."""

    path = Path(path)
    if schema_path is None:
        schema_path = _repo_root() / "schema" / "scene.schema.json"

    scene = yaml.safe_load(path.read_text())
    schema = json.loads(schema_path.read_text())
    validate(scene, schema)
    return scene


def _point_map(scene: Dict) -> Dict[str, Tuple[float, float]]:
    return {p["id"]: (p["x"], p["y"]) for p in scene.get("points", [])}


def _primitive_map(scene: Dict) -> Dict[str, Dict]:
    return {p["id"]: p for p in scene.get("primitives", [])}


def _line_points(prim: Dict, points: Dict[str, Tuple[float, float]]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    return points[prim["p1"]], points[prim["p2"]]


def _unit(vec: Tuple[float, float]) -> Tuple[float, float]:
    vx, vy = vec
    norm = math.hypot(vx, vy)
    if norm == 0:
        return 0.0, 0.0
    return vx / norm, vy / norm


def _angle_between(a: float, b: float) -> float:
    diff = (b - a) % (2 * math.pi)
    if diff > math.pi:
        diff -= 2 * math.pi
    return diff


def _format_float(val: float) -> str:
    return f"{val:.1f}".rstrip("0").rstrip(".") if not val.is_integer() else str(int(val))


def _angle_arc_path(
    points: Dict[str, Tuple[float, float]],
    primitives: Dict[str, Dict],
    symbol: Dict,
    radius: float = 20.0,
) -> str:
    line_a, line_b, vertex_id = symbol["targets"]
    vx, vy = points[vertex_id]

    def line_angle(line_id: str) -> float:
        prim = primitives[line_id]
        assert prim["type"] == "Line", "angle_arc expects line primitives"
        p1, p2 = prim["p1"], prim["p2"]
        if p1 == vertex_id:
            tx, ty = points[p2]
        elif p2 == vertex_id:
            tx, ty = points[p1]
        else:
            # Fallback: use midpoint direction to vertex.
            (x1, y1), (x2, y2) = _line_points(prim, points)
            tx, ty = (x1 + x2) / 2, (y1 + y2) / 2
        return math.atan2(ty - vy, tx - vx)

    ang_a = line_angle(line_a)
    ang_b = line_angle(line_b)

    delta = _angle_between(ang_a, ang_b)
    if delta < 0:
        start, end = ang_b, ang_a
        delta = -delta
    else:
        start, end = ang_a, ang_b

    large_arc = 1 if abs(delta) > math.pi else 0
    sweep_flag = 1

    sx = vx + radius * math.cos(start)
    sy = vy + radius * math.sin(start)
    ex = vx + radius * math.cos(end)
    ey = vy + radius * math.sin(end)

    return (
        f"M {_format_float(sx)} {_format_float(sy)} "
        f"A {radius:.0f} {radius:.0f} 0 {large_arc} {sweep_flag} {_format_float(ex)} {_format_float(ey)}"
    )


def render_svg(scene: Dict, svg_path: Path, canvas_size: int = CANVAS_SIZE) -> Path:
    """Render an SVG for the provided scene and write it to ``svg_path``."""

    svg_path = Path(svg_path)
    svg_path.parent.mkdir(parents=True, exist_ok=True)

    points = _point_map(scene)
    primitives = _primitive_map(scene)

    drawing = svgwrite.Drawing(
        filename=str(svg_path),
        size=(canvas_size, canvas_size),
        viewBox=f"0 0 {canvas_size} {canvas_size}",
    )
    drawing.attribs["id"] = svg_path.stem

    drawing.defs.add(drawing.style(STYLE_BLOCK))

    group_primitives = drawing.g(id="primitives")
    group_symbols = drawing.g(id="symbols")
    group_labels = drawing.g(id="labels")

    # Draw primitives in listed order for determinism.
    for prim in scene.get("primitives", []):
        prim_id = prim["id"]
        if prim["type"] == "Circle":
            cx, cy = points[prim["center"]]
            group_primitives.add(
                drawing.circle(center=(cx, cy), r=prim["radius"], id=prim_id, class_="prim")
            )
        elif prim["type"] == "Line":
            (x1, y1), (x2, y2) = _line_points(prim, points)
            group_primitives.add(
                drawing.line(start=(x1, y1), end=(x2, y2), id=prim_id, class_="prim")
            )
        elif prim["type"] == "Arc":
            circle = primitives[prim["circle"]]
            cx, cy = points[circle["center"]]
            radius = circle["radius"]
            start = points[prim["start"]]
            end = points[prim["end"]]
            large_arc = 1 if prim.get("measure_deg", 0) > 180 else 0
            path_d = (
                f"M {_format_float(start[0])} {_format_float(start[1])} "
                f"A {radius} {radius} 0 {large_arc} 1 {_format_float(end[0])} {_format_float(end[1])}"
            )
            group_primitives.add(
                drawing.path(d=path_d, id=prim_id, class_="prim")
            )
        else:
            raise ValueError(f"Unsupported primitive type: {prim['type']}")

    # Draw symbols.
    for symbol in scene.get("symbols", []):
        sym_id = symbol["id"]
        sym_type = symbol["type"]
        if sym_type == "angle_arc":
            path_d = _angle_arc_path(points, primitives, symbol)
            group_symbols.add(
                drawing.path(d=path_d, id=sym_id, class_="sym")
            )
        elif sym_type == "perpendicular":
            line_a_id, line_b_id = symbol["targets"][:2]
            line_a = primitives[line_a_id]
            line_b = primitives[line_b_id]
            pts_a = {line_a["p1"], line_a["p2"]}
            pts_b = {line_b["p1"], line_b["p2"]}
            intersection = pts_a & pts_b
            if intersection:
                vertex_id = next(iter(intersection))
                vx, vy = points[vertex_id]
            else:
                # Numeric intersection fallback.
                (xa1, ya1), (xa2, ya2) = _line_points(line_a, points)
                (xb1, yb1), (xb2, yb2) = _line_points(line_b, points)
                vx, vy = _line_intersection((xa1, ya1), (xa2, ya2), (xb1, yb1), (xb2, yb2))
            size = 8
            group_symbols.add(
                drawing.rect(
                    insert=(vx - size / 2, vy - size / 2),
                    size=(size, size),
                    id=sym_id,
                    class_="sym",
                )
            )
        elif sym_type == "tangent_mark":
            line_id, point_id = symbol["targets"][:2]
            px, py = points[point_id]
            line = primitives[line_id]
            (x1, y1), (x2, y2) = _line_points(line, points)
            direction = _unit((x2 - x1, y2 - y1))
            normal = (-direction[1], direction[0])
            offset_scale = 10
            tx = px + normal[0] * offset_scale
            ty = py + normal[1] * offset_scale
            group_symbols.add(
                drawing.text("⊥", insert=(tx, ty), id=sym_id, class_="lbl")
            )
        elif sym_type == "tick_bar":
            line_id = symbol["targets"][0]
            line = primitives[line_id]
            (x1, y1), (x2, y2) = _line_points(line, points)
            midx, midy = (x1 + x2) / 2, (y1 + y2) / 2
            dir_vec = _unit((x2 - x1, y2 - y1))
            perp = (-dir_vec[1], dir_vec[0])
            half_len = 6
            sx = midx - perp[0] * half_len
            sy = midy - perp[1] * half_len
            ex = midx + perp[0] * half_len
            ey = midy + perp[1] * half_len
            group_symbols.add(
                drawing.line(start=(sx, sy), end=(ex, ey), id=sym_id, class_="sym")
            )
        elif sym_type == "parallel":
            for idx, target in enumerate(symbol["targets"]):
                line = primitives[target]
                (x1, y1), (x2, y2) = _line_points(line, points)
                dir_vec = _unit((x2 - x1, y2 - y1))
                perp = (-dir_vec[1], dir_vec[0])
                offset = 10 + idx * 6
                midx, midy = (x1 + x2) / 2, (y1 + y2) / 2
                base = (midx + perp[0] * offset, midy + perp[1] * offset)
                stroke_half = 4
                start = (
                    base[0] - dir_vec[0] * stroke_half,
                    base[1] - dir_vec[1] * stroke_half,
                )
                end = (
                    base[0] + dir_vec[0] * stroke_half,
                    base[1] + dir_vec[1] * stroke_half,
                )
                group_symbols.add(
                    drawing.line(start=start, end=end, id=f"{sym_id}_{idx}", class_="sym")
                )
        else:
            raise ValueError(f"Unsupported symbol type: {sym_type}")

    # Point markers
    for point_id, (x, y) in points.items():
        group_labels.add(
            drawing.circle(center=(x, y), r=3, id=f"pt_{point_id}", class_="pt")
        )

    # Text labels and measures.
    for text in scene.get("texts", []):
        anchor = text["anchor"]
        if anchor not in points:
            continue
        ax, ay = points[anchor]
        content = text["string"]
        cls = "measure" if content.strip().endswith("°") else "lbl"
        if cls == "measure":
            dx, dy = -28, -10
        else:
            dx, dy = 8, -8
        group_labels.add(
            drawing.text(content, insert=(ax + dx, ay + dy), id=text["id"], class_=cls)
        )

    drawing.add(group_primitives)
    drawing.add(group_symbols)
    drawing.add(group_labels)

    drawing.save()
    return svg_path


def _line_intersection(
    a1: Tuple[float, float],
    a2: Tuple[float, float],
    b1: Tuple[float, float],
    b2: Tuple[float, float],
) -> Tuple[float, float]:
    """Return the intersection point of two infinite lines defined by endpoints."""

    x1, y1 = a1
    x2, y2 = a2
    x3, y3 = b1
    x4, y4 = b2

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if denom == 0:
        return x1, y1
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return px, py


def export_pngs(svg_path: Path, base_path: Path) -> List[Path]:
    """Best-effort raster export for common DPIs.

    If ``cairosvg`` is unavailable, the function simply returns an empty list so
    the CLI can continue without failing the build.
    """

    svg_path = Path(svg_path)
    base_path = Path(base_path)
    try:
        import cairosvg
    except ImportError:
        return []

    outputs: List[Path] = []
    svg_bytes = svg_path.read_bytes()
    for tag, dpi in (("96", 96), ("144", 144), ("300", 300)):
        out_file = base_path.with_name(f"{base_path.name}_{tag}").with_suffix(".png")
        cairosvg.svg2png(bytestring=svg_bytes, write_to=str(out_file), dpi=dpi)
        outputs.append(out_file)
    return outputs


def export_pgdp(scene: Dict, out_path: Path) -> Path:
    """Write PGDP-style annotations derived from the validated scene."""

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pgdp = {
        "points": scene.get("points", []),
        "lines": [p for p in scene.get("primitives", []) if p.get("type") == "Line"],
        "circles": [p for p in scene.get("primitives", []) if p.get("type") == "Circle"],
        "arcs": [p for p in scene.get("primitives", []) if p.get("type") == "Arc"],
        "symbols": scene.get("symbols", []),
        "texts": scene.get("texts", []),
        "relations": scene.get("relations", []),
    }

    out_path.write_text(json.dumps(pgdp, indent=2))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render symbol-grounded scenes to SVG/PNG/PGDP.")
    parser.add_argument("--scene", required=True, help="Path to scene YAML")
    parser.add_argument("--out_dir", required=True, help="Output directory for artifacts")
    parser.add_argument("--skip-png", action="store_true", help="Skip raster exports (faster for tests)")
    args = parser.parse_args()

    scene_path = Path(args.scene)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scene = load_scene(scene_path)

    base_name = out_dir.name
    svg_path = out_dir / f"{base_name}.svg"
    render_svg(scene, svg_path)

    export_pgdp(scene, out_dir / f"{base_name}.pgdp.json")

    if not args.skip_png:
        export_pngs(svg_path, out_dir / base_name)


if __name__ == "__main__":
    main()
