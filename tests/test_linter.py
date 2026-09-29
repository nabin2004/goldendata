from pathlib import Path
from manim_aos_data.linter import lint_sample

FX = Path(__file__).parent / "fixtures"
good = (FX / "good_derivative.txt").read_text()

def append_code(text, line):
    """Append a line inside the python block (before the closing fence)."""
    return text.rstrip().removesuffix("```").rstrip() + "\n" + line + "\n```\n"

def rules(text):
    return {i.rule for i in lint_sample(text, use_manim=False)}

def test_good_passes():
    assert rules(good) == set()

def test_bookmark_mismatch():
    assert "BOOKMARK_SET_EQUALITY" in rules(good.replace('wait_until_bookmark("b2")', 'wait_until_bookmark("zz")'))

def test_bookmark_outside_voiceover():
    bad = append_code(good, '        self.wait_until_bookmark("b1")')
    assert "BOOKMARK_AST_ORDER" in rules(bad)

def test_deprecated():
    assert "DEPRECATED_API_BAN" in rules(good.replace("Create(axes)", "ShowCreation(axes)"))

def test_banned_kwarg():
    assert "KWARG_SIGNATURE_CHECK" in rules(good.replace("color=RED", "color=RED, element_color=RED"))

def test_raw_latex():
    assert "RAW_LATEX_PREFIX" in rules(good.replace('MathTex(r"f(x)', 'MathTex("f(x)'))

def test_unicode_math():
    assert "UNICODE_MATH_BAN" in rules(good.replace('x^2")', 'x²")'))

def test_camera_pair():
    bad = append_code(good.replace("VoiceoverScene)", "VoiceoverScene, MovingCameraScene)"), "        self.play(self.camera.frame.animate.scale(0.8))")
    assert "CAMERA_RESTORE_PAIR" in rules(bad)

def test_not_two_block():
    assert "STRUCTURE" in rules("Sure! here you go\n" + good)
