
import pathlib
def test_svg_has_groups_and_ids():
    svg_path = pathlib.Path("items/T1/T1.svg")
    assert svg_path.exists(), "Run: make render"
    svg = svg_path.read_text()
    assert 'id="primitives"' in svg
    assert 'id="symbols"' in svg
    assert 'id="labels"' in svg
    assert 'id="ang_PAB"' in svg
    assert 'id="tangA"' in svg
