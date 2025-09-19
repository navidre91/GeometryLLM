#!/usr/bin/env python3
"""
Variant generator: applies contrastive/cosmetic ops to scene and re-renders.
Usage:
  python tools/make_variants.py --scene items/T1/scene.yaml --variants items/T1/T1.variants.json --out_dir items/T1
"""
import os, sys, json, argparse, copy, re, subprocess
from pathlib import Path
import yaml

def load_json(p): return json.load(open(p,'r',encoding='utf-8'))
def load_yaml(p): return yaml.safe_load(open(p,'r',encoding='utf-8'))

def save_yaml(obj, p): yaml.safe_dump(obj, open(p,'w',encoding='utf-8'), sort_keys=False, allow_unicode=True)

def remove_symbol_or_text(scene, sid):
    scene["symbols"] = [s for s in scene.get("symbols",[]) if s.get("id") != sid]
    scene["texts"]   = [t for t in scene.get("texts",[]) if t.get("id") != sid]
    scene["relations"] = [
        r for r in scene.get("relations",[]) if
        not ( (r.get("type")=="sym2geo" and r.get("symbol_id")==sid) or
              (r.get("type")=="text2geo" and r.get("text_id")==sid) )
    ]
    return scene

def nudge_label(scene, text_id, dx, dy):
    for t in scene.get("texts",[]):
        if t.get("id")==text_id:
            off = t.get("offset",[0,0])
            if len(off)<2: off=[0,0]
            t["offset"] = [off[0]+dx, off[1]+dy]
    return scene

def swap_labels(scene, t1, t2):
    T = scene.get("texts",[])
    a = next((x for x in T if x.get("id")==t1), None)
    b = next((x for x in T if x.get("id")==t2), None)
    if a and b:
        a["string"], b["string"] = b["string"], a["string"]
    return scene

def apply_ops(scene, ops):
    params = {"rotate":0.0, "symbol_opacity":1.0}
    if not ops: return scene, params
    for op in ops:
        if op.startswith("rotate"):
            m = re.match(r"rotate(-?\d+)", op)
            if m: params["rotate"] = float(m.group(1))
        elif op=="thin_symbols":
            params["symbol_opacity"] = 0.5
        elif op.startswith("remove_symbol:"):
            sid = op.split(":",1)[1]
            scene = remove_symbol_or_text(scene, sid)
        elif op.startswith("nudge:"):
            body = op.split(":",1)[1]
            tid,rest = body.split(":")
            dx,dy = rest.split(",")
            scene = nudge_label(scene, tid, float(dx), float(dy))
        elif op.startswith("swap:"):
            _, pair = op.split(":",1)
            t1,t2 = pair.split(",")
            scene = swap_labels(scene, t1, t2)
    return scene, params

def call_renderer(scene_path, out_dir, rotate, symbol_opacity):
    ROOT = Path(__file__).resolve().parents[1]
    render = ROOT / "tools" / "render_svg.py"
    cmd = [
        sys.executable, str(render),
        "--scene", str(scene_path),
        "--out_dir", str(out_dir),
        "--rotate", str(rotate),
        "--symbol_opacity", str(symbol_opacity),
    ]
    subprocess.check_call(cmd, cwd=str(ROOT))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--variants", required=True)
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()

    base_scene = load_yaml(args.scene)
    variants = load_json(args.variants)

    for v in variants:
        scene = copy.deepcopy(base_scene)
        ops = v.get("render_ops", [])
        for sid in v.get("mark_removed", []):
            scene = remove_symbol_or_text(scene, sid)
        scene, params = apply_ops(scene, ops)
        tmp_scene = Path(args.out_dir) / f"{Path(args.scene).stem}.{v['variant_id']}.tmp.yaml"
        save_yaml(scene, tmp_scene)
        call_renderer(tmp_scene, Path(args.out_dir), params["rotate"], params["symbol_opacity"])
        if v.get("image"):
            src = Path(args.out_dir) / f"{Path(args.scene).stem}.svg"
            dst = Path(args.out_dir) / v["image"]
            if src.exists():
                src.replace(dst)
        try: tmp_scene.unlink()
        except Exception: pass

    print("[make_variants] Done.")

if __name__ == "__main__":
    main()
