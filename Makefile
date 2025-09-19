install:
\tpip install -r requirements.txt

render:
\tpython tools/render_svg.py --scene items/T1/scene.yaml --out_dir items/T1

variants:
\tpython tools/make_variants.py --scene items/T1/scene.yaml --variants items/T1/T1.variants.json --out_dir items/T1

validate:
\tpython tools/validate_gold.py --items_dir items

test:
\tpytest -q

eval:
\tpython eval/evaluate.py --items_dir items --responses_dir runs/sample --out results.csv
