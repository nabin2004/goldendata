from pathlib import Path
from manim_aos_data.sample import parse_response, PLAN_KEYS

def test_parse_good():
    s = parse_response((Path(__file__).parent / "fixtures/good_derivative.txt").read_text())
    assert not s.errors and list(s.plan) == PLAN_KEYS
