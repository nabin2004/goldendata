"""Stage 1: cheap static triage of raw examples."""
import ast, re

def triage(code: str) -> dict:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"ok": False, "reason": "SYNTAX_ERROR", "detail": str(e)}
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if not classes:
        return {"ok": False, "reason": "NO_SCENE"}
    base_names = [ast.unparse(b) for c in classes for b in c.bases]
    return {
        "ok": True, "classes": [c.name for c in classes], "bases": base_names,
        "has_voiceover": any("VoiceoverScene" in b for b in base_names),
        "uses_manimlib": bool(re.search(r"manimlib", code)),
        "uses_shows_creation": "ShowCreation" in code,
        "has_camera": "camera.frame" in code,
        "n_lines": code.count("\n") + 1,
    }
