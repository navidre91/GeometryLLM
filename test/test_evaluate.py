import json, pathlib
from eval.evaluate import grounding_prf

def test_grounding_prf_basic():
    used = ["OT ⟂ PA", "∠PAB = 31°"]
    truth = {"OT ⟂ PA", "∠PAB = 31°", "PA tangent@A"}
    P,R,F1 = grounding_prf(used, truth)
    assert 0.66 <= P <= 1.0 and 0.66 <= R <= 1.0
