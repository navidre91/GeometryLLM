#!/usr/bin/env python3
"""
Deterministic SVG renderer for geometry scenes.

Usage:
  python tools/render_svg.py --scene items/T1/scene.yaml --out_dir items/T1 [--rotate 0] [--symbol_opacity 1.0]

- Reads scene.yaml (validates against schema/scene.schema.json if available)
- Renders layered SVG with stable IDs for primitives, symbols, labels
- Exports 96/144/300 DPI PNGs (requires cairosvg)
- Writes PGDP-like annotations (mirrors scene) to <ID>.pgdp.json
"""
import os, sys, json, math, argparse, re
from pathlib import Path

try:
    import yaml
except Exception as e:
    print("Missing dependency: pyyaml", file=sys.stderr); raise

def load_json(p):
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_yaml(p):
    with open(p, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def try_validate_scene(scene, schema_path: Path):
    try:
        import jsonschema
        schema = load_json(schema_path)
        jsonschema.validate(scene, schema)
    except Exception as e:
        # soft-fail: print but continue
        print(f"[render_svg] Schema validation warning: {e}", file=sys.stderr)

def points_dict(scene):
    return {p["id"]: (float(p["x"]), float(p["y"])) for p in scene.get("points",[])}

def find_primitive(scene, pid):
    for p in scene.get("primitives",[]):
        if p.get("id")==pid:
            return p
    return None

def find_line_pts(scene, line_id):
    L = find_primitive(scene, line_id)
    if not L or L.get("type")!="Line": return None
    pts = points_dict(scene)
    return pts[L["p1"]], pts[L["p2"]]

def line_intersection(p1, p2, p3, p4):
    # returns intersection point of lines p1p2 and p3p4
    x1,y1 = p1; x2,y2 = p2; x3,y3 = p3; x4,y4 = p4
    den = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(den) < 1e-9:
        return None
    px = ((x1*y2 - y1*x2)*(x3-x4) - (x1-x2)*(x3*y4 - y3*x4)) / den
    py = ((x1*y2 - y1*x2)*(y3-y4) - (y1-y2)*(x3*y4 - y3*x4)) / den
    return (px,py)

def svg_header(width, height, root_id="scene"):
    return f'''<svg id="{root_id}" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <style><![CDATA[
      .prim {{ fill: none; stroke: black; stroke-width: 2; }}
      .sym  {{ fill: none; stroke: black; stroke-width: 2; }}
      .lbl  {{ font-family: Arial, sans-serif; font-size: 14px; }}
      .measure {{ font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; }}
      .pt   {{ fill: black; }}
    ]]></style>
  </defs>
'''

def svg_footer():
    return '</svg>\n'

def draw_primitives(scene):
    pts = points_dict(scene)
    xs = [p[0] for p in pts.values()] + [0,400]; ys = [p[1] for p in pts.values()] + [0,400]
    width  = int(max(xs)+60); height = int(max(ys)+60)
    parts = []
    parts.append('  <g id="primitives">')
    for prim in scene.get("primitives",[]):
        if prim["type"]=="Circle":
            cx,cy = pts[prim["center"]]; r = prim["radius"]
            parts.append(f'    <circle id="{prim["id"]}" class="prim" cx="{cx}" cy="{cy}" r="{r}" />')
    for prim in scene.get("primitives",[]):
        if prim["type"]=="Line":
            (x1,y1),(x2,y2) = find_line_pts(scene, prim["id"])
            parts.append(f'    <line id="{prim["id"]}" class="prim" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" />')
    for prim in scene.get("primitives",[]):
        if prim["type"]=="Arc":
            circle = find_primitive(scene, prim["circle"])
            cx,cy = pts[circle["center"]]; r = circle["radius"]
            sx,sy = pts[prim["start"]]; ex,ey = pts[prim["end"]]
            laf = 1 if abs(prim.get("measure_deg",0)) > 180 else 0
            swf = 1
            parts.append(f'    <path id="{prim["id"]}" class="prim" d="M {sx:.3f} {sy:.3f} A {r:.3f} {r:.3f} 0 {laf} {swf} {ex:.3f} {ey:.3f}" />')
    parts.append('  </g>')
    return width, height, "\n".join(parts)+"\n"

def unit_vec(dx,dy):
    n = math.hypot(dx,dy) or 1.0
    return dx/n, dy/n

def perp_vec(dx,dy):
    return -dy, dx

def draw_symbol_angle_arc(scene, sym):
    pts = points_dict(scene)
    line1, line2, vtx = sym["targets"]
    (x1a,y1a),(x1b,y1b) = find_line_pts(scene, line1)
    (x2a,y2a),(x2b,y2b) = find_line_pts(scene, line2)
    vx,vy = pts[vtx]
    v1 = unit_vec(x1a - vx, y1a - vy) if (x1a,y1a)!=(vx,vy) else unit_vec(x1b - vx, y1b - vy)
    v2 = unit_vec(x2a - vx, y2a - vy) if (x2a,y2a)!=(vx,vy) else unit_vec(x2b - vx, y2b - vy)
    r = 18.0
    s = (vx + v1[0]*r, vy + v1[1]*r)
    e = (vx + v2[0]*r, vy + v2[1]*r)
    cross = v1[0]*v2[1] - v1[1]*v2[0]
    swf = 1 if cross>0 else 0
    path = f'M {s[0]:.1f} {s[1]:.1f} A {r:.1f} {r:.1f} 0 0 {swf} {e[0]:.1f} {e[1]:.1f}'
    return f'    <path id="{sym["id"]}" class="sym" d="{path}" />'

def draw_symbol_perpendicular(scene, sym):
    line1, line2 = sym["targets"][0], sym["targets"][1]
    (a1,a2) = find_line_pts(scene, line1)
    (b1,b2) = find_line_pts(scene, line2)
    p = line_intersection(a1,a2,b1,b2) or a2
    sz = 8.0; x = p[0]-sz/2; y = p[1]-sz/2
    return f'    <rect id="{sym["id"]}" class="sym" x="{x:.1f}" y="{y:.1f}" width="{sz:.1f}" height="{sz:.1f}" />'

def draw_symbol_parallel(scene, sym):
    def chevrons_for_line(scene, line_id, sym_id_suffix):
        (p1,p2) = find_line_pts(scene, line_id)
        dx,dy = (p2[0]-p1[0], p2[1]-p1[1])
        ux,uy = unit_vec(dx,dy); nx,ny = unit_vec(*perp_vec(dx,dy))
        midx = p1[0] + 0.3*dx; midy = p1[1] + 0.3*dy
        L = 10.0
        parts = []
        for i in (-1,1):
            ax = midx + nx*i*5; ay = midy + ny*i*5
            bx = ax + ux*L;     by = ay + uy*L
            parts.append(f'    <line id="{sym_id_suffix}_{i}" class="sym" x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" />')
        return "\n".join(parts)
    l1, l2 = sym["targets"][0], sym["targets"][1]
    return chevrons_for_line(scene, l1, sym["id"]+"_l1") + "\n" + chevrons_for_line(scene, l2, sym["id"]+"_l2")

def draw_symbol_tangent(scene, sym):
    line_id, point_id = sym["targets"][0], sym["targets"][1]
    pts = points_dict(scene); x,y = pts[point_id]
    return f'    <text id="{sym["id"]}" class="lbl" x="{x+10:.1f}" y="{y-10:.1f}">⊥</text>'

def draw_symbol_tick_bar(scene, sym):
    line_id = sym["targets"][0]
    (p1,p2) = find_line_pts(scene, line_id)
    dx,dy = (p2[0]-p1[0], p2[1]-p1[1])
    ux,uy = unit_vec(dx,dy); nx,ny = unit_vec(*perp_vec(dx,dy))
    midx = (p1[0]+p2[0])/2; midy = (p1[1]+p2[1])/2
    L = 10.0
    ax = midx + nx*L/2; ay = midy + ny*L/2
    bx = midx - nx*L/2; by = midy - ny*L/2
    return f'    <line id="{sym["id"]}" class="sym" x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" />'

def draw_symbols(scene, opacity=1.0):
    parts = [f'  <g id="symbols" opacity="{opacity}">']
    for sym in scene.get("symbols",[]):
        t = sym.get("type")
        if t=="angle_arc":
            parts.append(draw_symbol_angle_arc(scene, sym))
        elif t=="perpendicular":
            parts.append(draw_symbol_perpendicular(scene, sym))
        elif t=="parallel":
            parts.append(draw_symbol_parallel(scene, sym))
        elif t=="tangent_mark":
            parts.append(draw_symbol_tangent(scene, sym))
        elif t=="tick_bar":
            parts.append(draw_symbol_tick_bar(scene, sym))
    parts.append('  </g>')
    return "\n".join(parts)+"\n"

def draw_labels(scene):
    pts = points_dict(scene)
    parts = ['  <g id="labels">']
    for pid, (x,y) in pts.items():
        parts.append(f'    <circle id="pt_{pid}" class="pt" cx="{x:.1f}" cy="{y:.1f}" r="3" />')
    for txt in scene.get("texts",[]):
        t = txt["string"]
        anchor = txt["anchor"]
        dx,dy = (0,0)
        if "offset" in txt and isinstance(txt["offset"], list) and len(txt["offset"])>=2:
            dx,dy = txt["offset"][:2]
        x,y = pts[anchor]
        klass = "measure" if re.search(r"\d+\s*°", t) else "lbl"
        parts.append(f'    <text id="{txt["id"]}" class="{klass}" x="{x+dx:.1f}" y="{y+dy:.1f}">{t}</text>')
    parts.append('  </g>')
    return "\n".join(parts)+"\n"

def wrap_rotation(svg_inner, width, height, angle_deg=0.0):
    if not angle_deg:
        return svg_inner
    cx,cy = width/2.0, height/2.0
    return f'  <g id="rot" transform="rotate({angle_deg:.2f} {cx:.1f} {cy:.1f})">\n' + svg_inner + '  </g>\n'

def export_pngs(svg_path: Path, base_name: str):
    try:
        import cairosvg
    except Exception as e:
        print("[render_svg] CairoSVG not available; skipping PNG export", file=sys.stderr)
        return
    svg_data = Path(svg_path).read_text(encoding='utf-8')
    for tag, dpi in [("96",96),("144",144),("300",300)]:
        out = svg_path.with_name(f"{base_name}_{tag}.png")
        cairosvg.svg2png(bytestring=svg_data.encode("utf-8"), write_to=str(out), dpi=dpi)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, help="Path to scene.yaml")
    ap.add_argument("--out_dir", required=True, help="Output directory (will be created)")
    ap.add_argument("--rotate", type=float, default=0.0, help="Rotate entire figure by degrees")
    ap.add_argument("--symbol_opacity", type=float, default=1.0, help="Opacity for symbol layer (0..1)")
    args = ap.parse_args()

    scene = load_yaml(args.scene)
    schema_path = Path("schema/scene.schema.json")
    if schema_path.exists():
        try_validate_scene(scene, schema_path)

    width, height, prim_svg = draw_primitives(scene)
    sym_svg = draw_symbols(scene, opacity=args.symbol_opacity)
    lbl_svg = draw_labels(scene)

    inner = prim_svg + sym_svg + lbl_svg
    rotated_inner = wrap_rotation(inner, width, height, args.rotate)
    svg = svg_header(width, height, root_id=Path(args.scene).stem) + rotated_inner + svg_footer()

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(args.scene).stem
    svg_path = out_dir / f"{base_name}.svg"
    svg_path.write_text(svg, encoding='utf-8')

    pgdp = {
        "points": scene.get("points",[]),
        "lines": [p for p in scene.get("primitives",[]) if p.get("type")=="Line"],
        "circles": [p for p in scene.get("primitives",[]) if p.get("type")=="Circle"],
        "arcs": [p for p in scene.get("primitives",[]) if p.get("type")=="Arc"],
        "symbols": scene.get("symbols",[]),
        "texts": scene.get("texts",[]),
        "relations": scene.get("relations",[])
    }
    (out_dir / f"{base_name}.pgdp.json").write_text(json.dumps(pgdp, indent=2), encoding="utf-8")

    export_pngs(svg_path, base_name)
    print(f"[render_svg] Wrote {svg_path} and PNGs to {out_dir}")

if __name__ == "__main__":
    main()
