import pathlib
def test_svg_has_groups_and_ids():
    svg = (pathlib.Path("items/T1")/"T1.svg").read_text()
    assert 'id="primitives"' in svg
    assert 'id="symbols"' in svg
    assert 'id="labels"' in svg
    # angle arc & tang mark present
    assert 'id="ang_PAB"' in svg
    assert 'id="tangA"' in svg
