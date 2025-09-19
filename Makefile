ITEM ?= T1

install:
	pip install -r requirements.txt

render:
	python tools/render_svg.py --scene items/$(ITEM)/scene.yaml --out_dir items/$(ITEM)

variants:
	python tools/make_variants.py --scene items/$(ITEM)/scene.yaml --variants items/$(ITEM)/$(ITEM).variants.json --out_dir items/$(ITEM)

validate:
	python tools/validate_gold.py --items_dir items --schema_dir schema

test:
	pytest -q

eval:
	python eval/evaluate.py --items_dir items --responses_dir runs/sample --out results.csv
