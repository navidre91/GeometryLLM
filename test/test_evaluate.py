
from eval.evaluate import grounding_prf
def test_grounding_prf_basic():
    truth = {"oa ⊥ pa", "pa tangent@ a", "ang_pab = 31°"}
    used  = ["OA ⟂ PA", "∠PAB = 31°"]
    P,R,F1 = grounding_prf(used, truth)
    assert 0.4 <= P <= 1.0 and 0.4 <= R <= 1.0
