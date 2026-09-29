"""Deterministic checks. Pure functions; no network."""
import ast, re, inspect
from dataclasses import dataclass
from pathlib import Path
import yaml
from ..sample import parse_response, plan_bookmarks

CFG = Path(__file__).resolve().parents[3] / "configs"
BOOKMARK_RE = re.compile(r"<bookmark mark=['\"](.*?)['\"]\s*/>")
UNI_SUB = dict(zip("₀₁₂₃₄₅₆₇₈₉ₙᵢⱼ", ["_0","_1","_2","_3","_4","_5","_6","_7","_8","_9","_n","_i","_j"]))
UNI_SUP = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ", ["^0","^1","^2","^3","^4","^5","^6","^7","^8","^9","^n"]))

@dataclass
class LintIssue:
    rule: str
    msg: str
    fixable: bool = False

def _yaml(name):
    return yaml.safe_load((CFG / name).read_text())

def _calls(tree):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]

def _fname(call):
    f = call.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None

def check_structure(tree, code):
    out = []
    scenes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if not scenes:
        return [LintIssue("STRUCTURE", "no class")]
    bases = {b.id for c in scenes for b in c.bases if isinstance(b, ast.Name)}
    # Accept both VoiceoverScene and Scene for flexibility
    if "VoiceoverScene" not in bases and "Scene" not in bases:
        out.append(LintIssue("STRUCTURE", "class must inherit VoiceoverScene or Scene"))
    if "camera.frame" in code and "MovingCameraScene" not in bases:
        out.append(LintIssue("STRUCTURE", "camera.frame used without MovingCameraScene"))
    ctor = next((f for c in scenes for f in c.body if isinstance(f, ast.FunctionDef) and f.name == "construct"), None)
    if ctor is None:
        return out + [LintIssue("STRUCTURE", "no construct()")]
    first = ctor.body[0]
    # Only require set_speech_service for VoiceoverScene classes
    if "VoiceoverScene" in bases:
        if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Call) and "set_speech_service" in ast.unparse(first)):
            out.append(LintIssue("STRUCTURE", "first statement of construct() must be set_speech_service(GTTSService())"))
    # For simple Scene classes, relax requirements
    if "def fit_in_frame" not in code or "self.fit_in_frame(" not in code:
        # Only require fit_in_frame for VoiceoverScene classes
        if "VoiceoverScene" in bases:
            out.append(LintIssue("STRUCTURE", "fit_in_frame must be defined and used", True))
    for tag in ["# [LAYOUT]"]:
        if tag not in code:
            out.append(LintIssue("STRUCTURE", f"missing section comment {tag}"))
    if not re.search(r"# \[BEAT \d+ \| sync: [^\]]+\]", code):
        out.append(LintIssue("STRUCTURE", "missing '# [BEAT n | sync: label]' comments"))
    return out

def check_bookmarks(tree, code, plan):
    out = []
    narr = set()
    for c in _calls(tree):
        if _fname(c) == "voiceover":
            for kw in c.keywords:
                if kw.arg == "text" and isinstance(kw.value, ast.Constant):
                    narr |= set(BOOKMARK_RE.findall(kw.value.value))
    waits = {c.args[0].value for c in _calls(tree) if _fname(c) == "wait_until_bookmark" and c.args and isinstance(c.args[0], ast.Constant)}
    if narr != waits:
        out.append(LintIssue("BOOKMARK_SET_EQUALITY", f"voiceover {sorted(narr)} vs waits {sorted(waits)}"))
    if plan is not None and plan_bookmarks(plan) != narr:
        out.append(LintIssue("BOOKMARK_SET_EQUALITY", f"Plan {sorted(plan_bookmarks(plan))} vs code {sorted(narr)}"))
    # AST order: each wait must sit inside a `with self.voiceover(...)`
    inside = set()
    for w in [n for n in ast.walk(tree) if isinstance(n, ast.With) and any(_fname(i.context_expr) == "voiceover" for i in n.items if isinstance(i.context_expr, ast.Call))]:
        inside |= {id(c) for c in ast.walk(w) if isinstance(c, ast.Call) and _fname(c) == "wait_until_bookmark"}
    for c in _calls(tree):
        if _fname(c) == "wait_until_bookmark" and id(c) not in inside:
            out.append(LintIssue("BOOKMARK_AST_ORDER", "wait_until_bookmark outside voiceover block"))
    return out

def check_deprecated(tree, code):
    dep = _yaml("deprecated_map.yaml")
    out = []
    for pat in dep["imports"]:
        if pat.split()[1] in code and "manimlib" in code:
            out.append(LintIssue("DEPRECATED_API_BAN", "manimlib import", True)); break
    for old in dep["calls"]:
        if re.search(rf"\b{old}\b", code):
            out.append(LintIssue("DEPRECATED_API_BAN", f"{old}", True))
    for m in dep["methods_banned_on_mobjects"]:
        if re.search(rf"\.\s*{m}\(", code):
            out.append(LintIssue("DEPRECATED_API_BAN", f".{m}() is not a Mobject method"))
    return out

def check_kwargs(tree, use_manim=True):
    banned = _yaml("banned_kwargs.yaml")["banned"]
    out = []
    manim = None
    if use_manim:
        try:
            import manim
        except ImportError:
            manim = None
    for c in _calls(tree):
        name = _fname(c)
        kws = {k.arg for k in c.keywords if k.arg}
        bad = kws & (set(banned.get("*", [])) | set(banned.get(name, [])))
        if bad:
            out.append(LintIssue("KWARG_SIGNATURE_CHECK", f"{name}: banned kwargs {sorted(bad)}", True))
            continue
        obj = getattr(manim, name, None) if manim and isinstance(c.func, ast.Name) else None
        if obj is None:
            continue
        names, open_kw = set(), False
        for k in (inspect.getmro(obj) if inspect.isclass(obj) else [obj]):
            fn = k.__init__ if inspect.isclass(k) else k
            try: sig = inspect.signature(fn)
            except (ValueError, TypeError): continue
            for n, p in sig.parameters.items():
                if p.kind is p.VAR_KEYWORD: open_kw = True
                else: names.add(n)
        if not open_kw and kws - names:
            out.append(LintIssue("KWARG_SIGNATURE_CHECK", f"{name}: unknown kwargs {sorted(kws - names)}"))
    return out

def check_latex(tree):
    out = []
    for c in _calls(tree):
        if _fname(c) in {"MathTex", "Tex"}:
            for a in c.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    seg = (ast.get_source_segment(_SRC[0], a) or "").lstrip()
                    if not seg[:1] in ("r", "R"):
                        out.append(LintIssue("RAW_LATEX_PREFIX", "MathTex/Tex string must be raw", True))
    return out

_SRC = [None]

def check_unicode_math(code):
    bad = [ch for ch in code if ch in UNI_SUB or ch in UNI_SUP]
    return [LintIssue("UNICODE_MATH_BAN", f"unicode sub/superscript {sorted(set(bad))}", True)] if bad else []

def check_camera(code):
    moves = "camera.frame.animate" in code or "camera.frame.set" in code
    if moves and not ("camera.frame.save_state()" in code and re.search(r"Restore\(\s*self\.camera\.frame\s*\)", code)):
        return [LintIssue("CAMERA_RESTORE_PAIR", "camera moved without save_state()+Restore")]
    return []

def check_layout(code):
    out = []
    if re.search(r"\b(?:frame_width|frame_height)\s*=\s*[\d.]+", code):
        out.append(LintIssue("LAYOUT_ABSOLUTE", "hard-coded frame size"))
    return out

def lint_sample(response_text: str, use_manim=True) -> list[LintIssue]:
    s = parse_response(response_text)
    issues = [LintIssue("STRUCTURE", e) for e in s.errors]
    if "NOT_TWO_BLOCK" in s.errors:
        return issues
    try:
        tree = ast.parse(s.code)
    except SyntaxError as e:
        return issues + [LintIssue("SYNTAX_ERROR", str(e))]
    _SRC[0] = s.code
    issues += check_structure(tree, s.code) + check_bookmarks(tree, s.code, s.plan)
    issues += check_deprecated(tree, s.code) + check_kwargs(tree, use_manim)
    issues += check_latex(tree) + check_unicode_math(s.code) + check_camera(s.code) + check_layout(s.code)
    return issues
