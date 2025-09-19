#!/usr/bin/env python3
"""
Evaluation harness:
- Computes Answer Accuracy
- Computes Grounding Precision / Recall / F1 (string-match against figure facts)
- Flags error codes (GP, TG, AC, LC, NS)
- Computes Contrastive Consistency for 'flip_or_invalidate' variants if both base and edited responses exist

Usage:
  python eval/evaluate.py --items_dir items --responses_dir runs/sample --out results.csv
"""
import os, sys, json, argparse, re, math
from pathlib import Path
from collections import defaultdict

def load_json(p):
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

def parse_number(s):
    m = re.search(r"(-?\d+(\.\d+)?)", s.replace(",", ""))
    return float(m.group(1)) if m else None

def normalize_fact(s: str) -> str:
    t = s.strip().lower()
    t = t.replace(",", " ")
    t = t.replace("∠", "angle ")
    t = t.replace("perpendicular", "⊥").replace("right angle", "⊥")
    t = t.replace("parallel", "∥")
    # collapse angle tokens like "angle a b c" -> "angle abc"
    t = re.sub(r"angle\s+([a-z])\s+([a-z])\s+([a-z])", lambda m: f"angle {''.join(m.groups())}", t)
    t = re.sub(r"angle\s+([a-z]{3})", lambda m: f"angle {m.group(1)}", t)
    # normalize tangent references (with or without spaces around '@')
    t = re.sub(r"tangent\s*(?:at|to|@)\s*", "tangent@", t)
    t = re.sub(r"\s*@\s*", "@", t)
    # normalize perpendicular-at-point expressions
    t = re.sub(r"⊥\s*at\s*([a-z0-9]+)", lambda m: f"⊥@{m.group(1)}", t)
    # align degree expressions so "= 20" and "= 20°" match
    t = re.sub(r"=\s*(-?\d+(?:\.\d+)?)\s*°", r"= \1", t)
    t = t.replace("°", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t

def truth_facts_from_pgdp(pgdp: dict) -> set[str]:
    facts = set()
    sym_map = {s["id"]: s for s in pgdp.get("symbols",[])}
    line_map = {line["id"]: line for line in pgdp.get("lines", [])}

    def line_points(line_id: str) -> set[str]:
        line = line_map.get(line_id)
        if not line:
            return set()
        return {line.get("p1"), line.get("p2")}

    for rel in pgdp.get("relations",[]):
        if rel.get("type")=="sym2geo":
            sid = rel["symbol_id"]; s = sym_map.get(sid,{})
            st = s.get("type")
            if st=="perpendicular":
                l1,l2 = rel["target_ids"][0], rel["target_ids"][1]
                facts.add(normalize_fact(f"{l1} ⊥ {l2}"))
                facts.add(normalize_fact(f"{l2} ⊥ {l1}"))
                intersection = line_points(l1) & line_points(l2)
                for point in intersection:
                    if point:
                        facts.add(normalize_fact(f"right angle at {point}"))
                        facts.add(normalize_fact(f"⊥ at {point}"))
            elif st=="parallel":
                l1,l2 = rel["target_ids"][0], rel["target_ids"][1]
                facts.add(normalize_fact(f"{l1} ∥ {l2}"))
                facts.add(normalize_fact(f"{l2} ∥ {l1}"))
            elif st=="tangent_mark":
                line,pt = rel["target_ids"][0], rel["target_ids"][1]
                facts.add(normalize_fact(f"{line} tangent@ {pt}"))
    text2geo = {r["text_id"]: r["target_id"] for r in pgdp.get("relations",[]) if r.get("type")=="text2geo"}
    for txt in pgdp.get("texts",[]):
        content = txt.get("string", "")
        if "°" in content or re.search(r"=\s*-?\d+(?:\.\d+)?", content):
            tid = txt["id"]
            target = text2geo.get(tid)
            if target:
                facts.add(normalize_fact(f"{target} = {content}"))
    return facts

def grounding_prf(used: list[str], truth: set[str]):
    used_n = [normalize_fact(u) for u in used]
    used_set = set(used_n)
    tp = len([u for u in used_set if u in truth])
    fp = len([u for u in used_set if u not in truth])
    fn = len([t for t in truth if t not in used_set])
    P = tp / (tp + fp) if (tp+fp)>0 else 0.0
    R = tp / (tp + fn) if (tp+fn)>0 else 0.0
    F1 = 2*P*R/(P+R) if (P+R)>0 else 0.0
    return P,R,F1

def invented_parallel(used: list[str], truth: set[str]):
    return any(("∥" in u) and (u not in truth) for u in [normalize_fact(x) for x in used])

def tangent_missing(truth: set[str], used: list[str]):
    needs = any("tangent@" in t for t in truth)
    used_norm = [normalize_fact(x) for x in used]
    has_tangent = any("tangent@" in u for u in used_norm)
    has_perp = any("⊥" in u for u in used_norm)
    return needs and not (has_tangent or has_perp)

def arc_chord_conflict(truth: set[str], used: list[str]):
    used_norm = " ".join([normalize_fact(x) for x in used])
    mentions_arc = "arc" in used_norm
    mentions_angle_id = "angle" in used_norm
    has_measures = any(("=" in t and "°" in t) for t in truth)
    return (mentions_arc or mentions_angle_id) and not has_measures

def label_anchor_violation(used: list[str]):
    used_norm = " ".join([normalize_fact(x) for x in used])
    return ("label position" in used_norm) or ("by where the label" in used_norm)

def mentions_visual_scale(pred_text: str):
    t = pred_text.lower()
    return any(k in t for k in ["by scale", "looks equal", "appears equal", "not to scale but", "visually"])

def evaluate_variant(item_id, variant, gold, pgdp, resp_path):
    if not resp_path.exists():
        return {"exists": False}
    resp = load_json(resp_path)
    pred = parse_number(resp.get("final_answer","") or "")
    gold_val = gold["answer"]["value"]; tol = float(gold["answer"].get("tol",0))
    acc = int(pred is not None and abs(pred - gold_val) <= tol)
    used = resp.get("figure_facts_used", [])
    truth = truth_facts_from_pgdp(pgdp)
    P,R,F1 = grounding_prf(used, truth)
    flags = []
    if invented_parallel(used, truth): flags.append("GP")
    if tangent_missing(truth, used):   flags.append("TG")
    if arc_chord_conflict(truth, used):flags.append("AC")
    if label_anchor_violation(used):   flags.append("LC")
    if mentions_visual_scale(json.dumps(resp)): flags.append("NS")
    return {"exists": True, "acc": acc, "P": P, "R": R, "F1": F1, "flags": ";".join(flags), "pred": pred}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items_dir", required=True)
    ap.add_argument("--responses_dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    items_dir = Path(args.items_dir)
    rows = []
    for item_dir in items_dir.iterdir():
        if not item_dir.is_dir(): continue
        item_id = item_dir.name
        gold = load_json(item_dir / f"{item_id}.gold.json")["gold"]
        pgdp = load_json(item_dir / f"{item_id}.pgdp.json")
        variants = load_json(item_dir / f"{item_id}.variants.json")
        preds = {}
        metrics = {}
        for v in variants:
            vid = v["variant_id"]
            resp_path = Path(args.responses_dir) / f"{vid}.json"
            res = evaluate_variant(item_id, v, gold, pgdp, resp_path)
            rows.append({
                "item": item_id,"variant": vid,
                "exists": int(res.get("exists",False)),
                "acc": res.get("acc",0),
                "P": f'{res.get("P",0):.3f}', "R": f'{res.get("R",0):.3f}', "F1": f'{res.get("F1",0):.3f}',
                "flags": res.get("flags","")
            })
            if res.get("exists"):
                preds[vid] = res.get("pred")
                metrics[vid] = res
        base_vid = next((v["variant_id"] for v in variants if v["variant_id"].endswith("full_txtimg")), None)
        mr_vid   = next((v["variant_id"] for v in variants if v["variant_id"].endswith("mark_removed")), None)
        if base_vid and mr_vid and base_vid in preds and mr_vid in preds:
            consistent = int(preds[base_vid] != preds[mr_vid])
            rows.append({"item": item_id, "variant": "contrastive_check",
                         "exists": 1, "acc": consistent, "P":"", "R":"", "F1":"", "flags": "CONSISTENCY"})

        def acc_for(vid: str):
            res = metrics.get(vid)
            return res.get("acc") if res else None

        img_vid = next((v["variant_id"] for v in variants if v["variant_id"].endswith("img_only")), None)
        txt_vid = next((v["variant_id"] for v in variants if v["variant_id"].endswith("txt_only")), None)

        base_acc = acc_for(base_vid) if base_vid else None
        img_acc = acc_for(img_vid) if img_vid else None
        txt_acc = acc_for(txt_vid) if txt_vid else None

        delta_img = (img_acc - base_acc) if (base_acc is not None and img_acc is not None) else None
        delta_txt = (txt_acc - base_acc) if (base_acc is not None and txt_acc is not None) else None

        delta_img_str = f"{delta_img:+d}" if isinstance(delta_img, int) else (f"{delta_img:+.2f}" if isinstance(delta_img, float) and delta_img is not None else "")
        delta_txt_str = f"{delta_txt:+d}" if isinstance(delta_txt, int) else (f"{delta_txt:+.2f}" if isinstance(delta_txt, float) and delta_txt is not None else "")

        sensitivity_exists = 1 if base_acc is not None else 0
        rows.append({
            "item": item_id,
            "variant": "variant_sensitivity",
            "exists": sensitivity_exists,
            "acc": "",
            "P": delta_img_str,
            "R": delta_txt_str,
            "F1": "",
            "flags": "SENSITIVITY"
        })

    outp = Path(args.out); outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w", encoding="utf-8") as f:
        f.write("item,variant,exists,acc,P,R,F1,flags\n")
        for r in rows:
            f.write(f'{r["item"]},{r["variant"]},{r["exists"]},{r["acc"]},{r["P"]},{r["R"]},{r["F1"]},{r["flags"]}\n')
    print(f"[evaluate] wrote {outp}")

if __name__ == "__main__":
    main()
