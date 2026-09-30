from pathlib import Path
from manim_aos_data.sample import parse_response, PLAN_KEYS

def test_parse_good():
    s = parse_response((Path(__file__).parent / "fixtures/good_derivative.txt").read_text())
    assert not s.errors and list(s.plan) == PLAN_KEYS


def test_parse_end_block():
    response = """<Plan>
goal: explain a derivative
skills: VoiceoverScene
layout: title top
camera: Static
dynamics: none
math: r"x"
narration: A short explanation.
validate: render passes
</Plan>
```python
from manim import *
```
<End>
  <WhatWasBuilt>A derivative scene.</WhatWasBuilt>
  <WhatWasDemonstrated>The slope idea.</WhatWasDemonstrated>
  <AnimationAndNarration>One narrated beat.</AnimationAndNarration>
  <ExpectedChecks>Bookmarks and render pass.</ExpectedChecks>
</End>"""
    sample = parse_response(response)
    assert not sample.errors
