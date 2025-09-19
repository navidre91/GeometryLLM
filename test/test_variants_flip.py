
import json, pathlib
def test_mark_removed_variant_declares_decisive_symbol():
    v = json.load(open("items/T1/T1.variants.json"))
    mr = [x for x in v if x["variant_id"].endswith("mark_removed")][0]
    assert "decisive_symbol" in mr
    assert mr["expected_effect"] == "flip_or_invalidate"
