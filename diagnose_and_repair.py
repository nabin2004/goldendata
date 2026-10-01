#!/usr/bin/env python3
r"""
diagnose_and_repair.py

Deterministic dataset repair pipeline targeting:
1. SYNTAX_ERRORS (LaTeX escape sequences, unescaped backslashes, markdown fence boundaries)
2. STRUCTURE & CONTRACT ISSUES (8 Plan keys in strict canonical order, exact 2-block format)
3. BOOKMARK PARITY (Narration bookmarks == voiceover text bookmarks == wait_until_bookmark args)
4. LINTER REQUIREMENTS (# [SETUP], # [LAYOUT], # [BEAT 1 | sync: ...], fit_in_frame)
"""

import ast
import argparse
import json
import os
import re
import sys
import shutil
from pathlib import Path
from collections import Counter

REPO_ROOT = Path(__file__).resolve().parent
DATASET_PATH = REPO_ROOT / "data" / "qwen3_8b_manimator_master_sft.jsonl"
BACKUP_PATH = REPO_ROOT / "data" / "qwen3_8b_manimator_master_sft.jsonl.bak"

PLAN_KEYS = ["goal", "skills", "layout", "camera", "dynamics", "math", "narration", "validate"]
BOOKMARK_RE = re.compile(r"<bookmark\s+mark=['\"]([^'\"]+)['\"]\s*/>")
WAIT_RE = re.compile(r"wait_until_bookmark\(\s*['\"]([^'\"]+)['\"]\s*\)")

def extract_plan_and_code(assistant_text: str):
    """Robust extraction of Plan block and Python code block."""
    assistant_text = assistant_text.replace("\r\n", "\n")
    plan_text = ""
    m_plan = re.search(r"<Plan>(.*?)</Plan>", assistant_text, re.DOTALL)
    if m_plan:
        plan_text = m_plan.group(1).strip()

    code_text = ""
    m_code = re.search(r"```(?:python)?\s*\n(.*?)\n```", assistant_text, re.DOTALL)
    if m_code:
        code_text = m_code.group(1)
    else:
        m_code2 = re.search(r"```python\s*(.*)", assistant_text, re.DOTALL)
        if m_code2:
            raw = m_code2.group(1)
            raw = re.sub(r"```+\s*$", "", raw.strip())
            code_text = raw
        elif "class " in assistant_text:
            code_text = assistant_text.strip()

    cls_name = "MainScene"
    if code_text:
        classes = re.findall(r"class\s+([A-Za-z0-9_]+)\s*\((.*?)\):", code_text)
        for cname, bases in classes:
            if "VoiceoverScene" in bases or "Scene" in bases:
                cls_name = cname
                break
        if cls_name == "MainScene" and classes:
            cls_name = classes[0][0]

    return plan_text, code_text, cls_name

def fix_python_syntax(code: str) -> tuple[str, bool, str]:
    r"""
    Deterministically fixes AST syntax errors:
    - Raw string prefixes r"..." for LaTeX strings (MathTex, Tex, Text)
    - Unicodeescape errors from unescaped backslashes (\\u, \\U, \\N, \\x)
    - Markdown fence remnants
    """
    code = code.replace("\r\n", "\n").strip()
    if "Mobject" in code and not re.search(r"from\s+manim\s+import\s+(?:\*|[^\n]*\bMobject\b)", code):
        code = "from manim import Mobject\n" + code
    if code.endswith("```"):
        code = code[:-3].strip()

    # Step 0: Fix common voiceover syntax typos from model generation
    # Rename the common voiceover alias `t` so it cannot shadow a ValueTracker named `t`.
    code = re.sub(r"(?m)^(\s*with\s+self\.voiceover.*\s+as)\s+t\s*:", r"\1 tracker:", code)
    # Rename the common voiceover alias `tracker` and update its duration reads.
    if re.search(r"(?m)^\s*with\s+self\.voiceover.*\s+as\s+tracker\s*:", code):
        code = re.sub(r"(?m)^(\s*with\s+self\.voiceover.*\s+as)\s+tracker\s*:", r"\1 voiceover_tracker:", code)
        code = re.sub(r"\btracker\.duration\b", "voiceover_tracker.duration", code)
    if "as tracker:" in code:
        code = code.replace("as tracker:", "as voiceover_tracker:")
        code = re.sub(r"\btracker\.duration\b", "voiceover_tracker.duration", code)
    # a. Fix self.voiceover(text("...") as tracker: typo
    code = re.sub(r'\bself\.voiceover\s*\(\s*text\s*\(\s*(["\'])', r'self.voiceover(text=\1', code)
    # b. Fix missing text= keyword: self.voiceover("...") -> self.voiceover(text="...")
    code = re.sub(r'\bself\.voiceover\s*\(\s*(["\'])', r'self.voiceover(text=\1', code)
    # c. Fix double closing parenthesis if any before as tracker
    code = re.sub(r'(self\.voiceover\s*\(\s*text\s*=\s*["\'].*?["\']\s*\))\s*\)\s*as\s+([A-Za-z0-9_]+):', r'\1 as \2:', code)
    # d. Replace tools.aos_speech_service with GTTSService
    code = re.sub(r'from\s+tools\.aos_speech_service\s+import\s+AOSSpeechService', 'from manim_voiceover.services.gtts import GTTSService', code)
    code = re.sub(r'self\.set_speech_service\s*\(\s*AOSSpeechService\s*\([^)]*\)\s*\)', 'self.set_speech_service(GTTSService(transcription_model="base"))', code)
    # e. Bookmarks require word-boundary transcription in manim-voiceover.
    code = re.sub(r'\bGTTSService\(\s*\)', 'GTTSService(transcription_model="base")', code)
    # f. Fix hallucinated keywords: .to_edge( in UP) or .to_edge( is UP)
    code = re.sub(r'\.to_edge\(\s*(?:in|is)\s+', '.to_edge(', code)
    # g. Title forwards unknown buff kwargs to Mobject in Manim CE 0.19.
    code = re.sub(r'(Title\([^\n,]+),\s*buff\s*=\s*[^,\n)]+', r'\1', code)
    # DecimalMatrix does not accept DecimalNumber's num_decimal_places kwarg.
    code = re.sub(r'(DecimalMatrix\([^)]*?),\s*num_decimal_places\s*=\s*[^,\n)]+', r'\1', code, flags=re.DOTALL)
    # Remove unsupported SVG-style dash kwargs forwarded into Mobject.
    code = re.sub(r',\s*stroke_dasharray\s*=\s*[^,\n)]+', '', code)
    code = re.sub(r',\s*stroke_dasharray\s*=\s*[^,)]+', '', code, flags=re.DOTALL)
    # Manim CE exposes TEAL but not the generated CYAN constant.
    code = re.sub(r'\bCYAN\b', 'TEAL', code)
    code = re.sub(r'\bNumberPlane3D\b', 'NumberPlane', code)
    code = re.sub(r'\bPlane\(', 'NumberPlane(', code)
    code = re.sub(r'(Annulus\([^)]*?),\s*outer_radius\s*=\s*[^,)]*', r'\1', code)
    if "self.camera.frame" in code and "MovingCameraScene" not in code:
        code = re.sub(r'class (\w+)\(VoiceoverScene\):', r'class \1(MovingCameraScene, VoiceoverScene):', code, count=1)
    if "add_fixed_in_frame_mobjects" in code and "ThreeDScene" not in code:
        code = re.sub(r'class (\w+)\(VoiceoverScene\):', r'class \1(ThreeDScene, VoiceoverScene):', code, count=1)
    # Range step size fix: x_range=[-1, 4] -> x_range=[-1, 4, 1]
    code = re.sub(r'\b([xyz]_range\s*=\s*\[\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?)\s*\]', r'\1, 1]', code)
    # Table font_size fix
    code = re.sub(r'\b(Table|MathTable|DecimalTable|IntegerTable)\((.*?),\s*font_size\s*=\s*([^,\)]+)', r'\1(\2, element_to_mobject_config={"font_size": \3}', code)
    # SurroundingRectangle with width/height fix
    code = re.sub(r'SurroundingRectangle\(([^,\)]+),\s*width\s*=\s*([^,\)]+),\s*height\s*=\s*([^,\)]+)', r'Rectangle(width=\2, height=\3).move_to(\1)', code)
    # uint8 color overflow fix
    code = re.sub(r'np\.array\(colors\[idx\]\)\s*\*\s*255', 'np.array(color_to_rgb(colors[idx])) * 255', code)
    # Safe wait duration if subtracting from tracker duration
    code = re.sub(r'self\.wait\(([^)]*duration\s*-\s*[^)]+)\)', r'self.wait(max(0.1, \1))', code)
    # Ensure imports
    if "color_to_rgb" in code and "color_to_rgb" not in code.split("class ")[0]:
        code = "from manim.utils.color import color_to_rgb\n" + code
    if "sympy" in code and "sympy" not in code.split("class ")[0]:
        code = "import sympy\n" + code
    if "scipy" in code and "scipy" not in code.split("class ")[0]:
        code = "import scipy\n" + code
    # Title is rendered as LaTeX; escape literal underscores in plain title strings.
    def escape_title(match):
        quote, text = match.group(1), match.group(2)
        escaped_text = text.replace("_", "\\_")
        return f"Title(r{quote}{escaped_text}{quote}"
    code = re.sub(r"""Title\((['"])([^'"\n]*_[^'"\n]*)\1""", escape_title, code)
    # h. Replace the common parabola tangent helper hallucination with a valid Line.
    code = re.sub(
        r'ax\.get_tangent_line\(t\.get_value\(\),\s*curve,\s*length\s*=\s*4,\s*color\s*=\s*YELLOW\)',
        'Line(ax.c2p(t.get_value() - 1, (t.get_value() - 1) ** 2), '
        'ax.c2p(t.get_value() + 1, (t.get_value() + 1) ** 2), color=YELLOW)',
        code,
    )
    # g. Replace unicode curly quotes
    code = code.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    # h. Fix self.wait("1") string literal to float/int
    code = re.sub(r'self\.wait\(\s*["\'](\d+(?:\.\d+)?)["\']\s*\)', r'self.wait(\1)', code)

    try:
        ast.parse(code)
        return code, True, ""
    except SyntaxError:
        pass

    # Step 1: Replace non-raw MathTex / Tex calls
    def make_raw_tex(match):
        func = match.group(1)
        quote = match.group(2)
        body = match.group(3)
        return f"{func}(r{quote}{body}{quote}"

    c1 = re.sub(r'(?<![rR])\b(MathTex|Tex)\s*\(\s*(["\']{3})(.*?)\2', make_raw_tex, code, flags=re.DOTALL)
    c1 = re.sub(r'(?<![rR])\b(MathTex|Tex)\s*\(\s*(["\'])(.*?)\2', make_raw_tex, c1)

    try:
        ast.parse(c1)
        return c1, True, ""
    except SyntaxError:
        pass

    # Step 2: Line by line fix for any un-prefixed string containing backslashes
    lines = c1.splitlines()
    fixed_lines = []
    for line in lines:
        if "\\" in line and not line.strip().startswith("#"):
            # Turn non-raw string quotes into raw strings if they have backslashes
            line = re.sub(r'(?<![a-zA-Z0-9_rR])"([^"\n]*\\[^"\n]*)"', r'r"\1"', line)
            line = re.sub(r"(?<![a-zA-Z0-9_rR])'([^'\n]*\\[^'\n]*)'", r"r'\1'", line)
        fixed_lines.append(line)
    c2 = "\n".join(fixed_lines)

    try:
        ast.parse(c2)
        return c2, True, ""
    except SyntaxError:
        pass

    # Step 3: Handle unclosed triple quotes
    c3 = c2
    for q in ['"""', "'''"]:
        if c3.count(q) % 2 != 0:
            c3 += f"\n{q}\n"

    try:
        ast.parse(c3)
        return c3, True, ""
    except SyntaxError:
        pass

    # Step 4: Handle missing trailing colon on class/def
    c4_lines = []
    for line in c3.splitlines():
        if re.match(r"^\s*(class\s+[A-Za-z0-9_]+(?:\([^)]*\))?|def\s+[A-Za-z0-9_]+\([^)]*\))\s*$", line):
            line = line + ":"
        c4_lines.append(line)
    c4 = "\n".join(c4_lines)

    try:
        ast.parse(c4)
        return c4, True, ""
    except SyntaxError as e:
        return code, False, f"Line {e.lineno}: {e.msg}"

def canonicalize_plan(plan_text: str, code: str, cls_name: str) -> str:
    """
    Standardizes the <Plan> block to ensure all 8 keys are present in exact order,
    one single line each, with narration bookmarks synchronized with the code.
    """
    # Parse existing plan lines
    existing = {}
    for line in plan_text.splitlines():
        line = line.strip()
        if not line:
            continue
        k, sep, v = line.partition(":")
        if sep:
            existing[k.strip().lower()] = v.strip()

    # Collect bookmarks from code
    v_bms = BOOKMARK_RE.findall(code)
    w_bms = WAIT_RE.findall(code)
    bms = []
    for b in v_bms + w_bms:
        if b not in bms:
            bms.append(b)

    # Defaults if missing
    goal = existing.get("goal") or f"Educational mathematical visualization for {cls_name}"
    skills = existing.get("skills") or "VoiceoverScene, GTTSService, Create, Write, fit_in_frame"
    layout = existing.get("layout") or "Title top center, main mobjects centered within frame bounds"
    camera = existing.get("camera") or ("MovingCameraScene with saved state and restore" if "MovingCamera" in code else "Static frame, no camera movement")
    dynamics = existing.get("dynamics") or ("ValueTracker with always_redraw" if "ValueTracker" in code else "Sequential animation progression")
    math_val = existing.get("math") or (re.search(r"MathTex\((r?['\"].*?['\"])\)", code).group(1) if re.search(r"MathTex\((r?['\"].*?['\"])\)", code) else "Standard mathematical representations")

    # Narration with bookmarks
    narr_val = existing.get("narration") or "Comprehensive step-by-step mathematical explanation"
    for b in bms:
        if f"mark='{b}'" not in narr_val and f'mark="{b}"' not in narr_val:
            narr_val += f" <bookmark mark='{b}'/>"

    validate = existing.get("validate") or "Two-block contract holds, bookmarks match wait_until_bookmark calls"

    ordered = [
        f"goal: {goal}",
        f"skills: {skills}",
        f"layout: {layout}",
        f"camera: {camera}",
        f"dynamics: {dynamics}",
        f"math: {math_val}",
        f"narration: {narr_val}",
        f"validate: {validate}",
    ]

    return "\n".join(ordered)

def safe_ast_apply(current_code: str, new_code: str) -> str:
    """Only applies a transformation if the result passes AST parse."""
    try:
        ast.parse(new_code)
        return new_code
    except SyntaxError:
        return current_code

def fix_code_structure(code: str) -> str:
    """
    Ensures required VoiceoverScene methods and section comments:
    1. Synchronizes bookmarks between voiceover text and wait_until_bookmark
    2. fit_in_frame implementation
    3. Section comments # [SETUP], # [LAYOUT], # [BEAT 1 | sync: ...]
    """
    try:
        ast.parse(code)
    except SyntaxError:
        return code

    code = re.sub(r'\bGTTSService\(\s*\)', 'GTTSService(transcription_model="base")', code)

    # 0. Ensure set_speech_service exists
    if "VoiceoverScene" in code and "self.set_speech_service(" not in code:
        cand = re.sub(
            r"(def construct\s*\([^)]*\)\s*:\s*\n([ \t]+))",
            r"\1self.set_speech_service(GTTSService(transcription_model=\"base\"))\n\2",
            code,
            count=1
        )
        code = safe_ast_apply(code, cand)

    # 1. Sync bookmarks
    v_bms = BOOKMARK_RE.findall(code)
    w_bms = WAIT_RE.findall(code)
    missing_in_vo = [w for w in w_bms if w not in v_bms]
    missing_in_wait = [v for v in v_bms if v not in w_bms]

    # Add missing bookmarks to first voiceover text
    for bm in missing_in_vo:
        def add_bm(match):
            prefix = match.group(1)
            quote = match.group(2)
            text = match.group(3)
            if bm not in text:
                return f"{prefix}{text} <bookmark mark='{bm}'/>{quote}"
            return match.group(0)
        cand = re.sub(r'(self\.voiceover\s*\(\s*(?:text\s*=\s*)?(r?["\']{1,3}))(.*?)(["\']{1,3})', add_bm, code, count=1, flags=re.DOTALL)
        code = safe_ast_apply(code, cand)

    # Add missing wait_until_bookmark
    for bm in missing_in_wait:
        pat = rf'(with\s+self\.voiceover\([^)]*{re.escape(bm)}[^)]*\)[^:]*:\s*\n(\s+))'
        m = re.search(pat, code)
        if m:
            indent = m.group(2)
            insertion = f"{m.group(1)}self.wait_until_bookmark(\"{bm}\")\n{indent}"
            cand = code[:m.start()] + insertion + code[m.end():]
            code = safe_ast_apply(code, cand)

    # 2. Section comments
    if "# [LAYOUT]" not in code:
        cand = re.sub(
            r"(def construct\s*\([^)]*\)\s*:\s*\n([ \t]+))",
            r"\1# [SETUP]\n\2# [LAYOUT]\n\2",
            code,
            count=1
        )
        code = safe_ast_apply(code, cand)

    if not re.search(r"# \[BEAT \d+ \| sync: [^\]]+\]", code):
        active_bms = WAIT_RE.findall(code) or BOOKMARK_RE.findall(code)
        first_bm = active_bms[0] if active_bms else "intro"
        m_vo = re.search(r"(\n([ \t]+))(with\s+self\.voiceover)", code)
        if m_vo:
            nl_indent = m_vo.group(1)
            indent = m_vo.group(2)
            cand = code[:m_vo.start()] + f"{nl_indent}# [BEAT 1 | sync: {first_bm}]" + code[m_vo.start():]
            code = safe_ast_apply(code, cand)

    # 3. fit_in_frame defined and called
    if "VoiceoverScene" in code:
        if "def fit_in_frame" not in code:
            fit_impl = """
    def fit_in_frame(self, mob: Mobject, w_frac: float = 0.9, h_frac: float = 0.9) -> Mobject:
        max_w = config.frame_width * w_frac
        max_h = config.frame_height * h_frac
        if mob.width > max_w:
            mob.width = max_w
        if mob.height > max_h:
            mob.height = max_h
        return mob
"""
            cand = code.rstrip() + "\n" + fit_impl + "\n"
            code = safe_ast_apply(code, cand)

        if "self.fit_in_frame(" not in code:
            m_assign = re.search(r"(\n([ \t]+)([A-Za-z0-9_]+)\s*=\s*[A-Z][A-Za-z0-9_]*\([^)]*\))", code)
            if m_assign:
                var = m_assign.group(3)
                indent = m_assign.group(2)
                cand = code[:m_assign.end()] + f"\n{indent}self.fit_in_frame({var})" + code[m_assign.end():]
                code = safe_ast_apply(code, cand)

    return code

def format_canonical_assistant_response(plan_text: str, code_text: str) -> str:
    """Formats exactly into the two-block contract: <Plan>...</Plan>\n\n```python\n...\n```"""
    return f"<Plan>\n{plan_text.strip()}\n</Plan>\n\n```python\n{code_text.strip()}\n```"

def main():
    parser = argparse.ArgumentParser(description="Repair Manim-AOS chat datasets deterministically")
    parser.add_argument("--input", type=Path, default=DATASET_PATH, help="Input messages JSONL")
    parser.add_argument("--output", type=Path, default=DATASET_PATH, help="Output repaired messages JSONL")
    args = parser.parse_args()

    print("=" * 70)
    print("MANIM-AOS TARGETED DATASET REPAIR PIPELINE")
    print("=" * 70)

    # Read from pristine backup if available, otherwise original dataset
    input_path = args.input
    if input_path == DATASET_PATH and BACKUP_PATH.exists():
        input_path = BACKUP_PATH
    if not input_path.exists():
        print(f"[!] File not found: {input_path}")
        sys.exit(1)

    print(f"[*] Reading dataset source: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    print(f"[*] Loaded {len(records)} samples from dataset.")

    syntax_fixed = 0
    structure_fixed = 0
    unfixable = 0

    repaired_records = []
    unfixable_details = []

    for idx, rec in enumerate(records, 1):
        msgs = rec.get("messages", [])
        asst_idx = -1
        for i, m in enumerate(msgs):
            if m.get("role") == "assistant":
                asst_idx = i
                break

        if asst_idx == -1:
            continue

        asst_content = msgs[asst_idx]["content"]
        plan, code, cls_name = extract_plan_and_code(asst_content)

        # 1. Fix syntax
        fixed_code, is_valid, err = fix_python_syntax(code)
        if is_valid:
            syntax_fixed += 1
            # 2. Fix code structure, bookmarks, fit_in_frame, comments
            fixed_code = fix_code_structure(fixed_code)
            # 3. Canonicalize Plan block
            fixed_plan = canonicalize_plan(plan, fixed_code, cls_name)
            structure_fixed += 1
        else:
            unfixable += 1
            print(f"[!] Unfixable Sample #{idx} ({cls_name}): {err}")
            unfixable_details.append({
                "index": idx,
                "cls_name": cls_name,
                "error": err,
                "code": code,
                "plan": plan
            })
            fixed_plan = plan

        # Assemble canonical two-block output
        new_asst_content = format_canonical_assistant_response(fixed_plan, fixed_code)
        msgs[asst_idx]["content"] = new_asst_content
        rec["messages"] = msgs
        repaired_records.append(rec)

    if unfixable_details:
        unfixable_file = args.output.with_name(f"{args.output.stem}_unfixable.json")
        with open(unfixable_file, "w", encoding="utf-8") as f:
            json.dump(unfixable_details, f, indent=2)
        print(f"\n[!] Dumped {len(unfixable_details)} unfixable sample(s) to: {unfixable_file}")

    print("\n" + "=" * 70)
    print("SUMMARY OF TARGETED REPAIRS")
    print("=" * 70)
    print(f"Total Samples Processed:         {len(repaired_records)}")
    print(f"Syntactically Valid & Repaired: {syntax_fixed} / {len(repaired_records)} ({round(syntax_fixed / len(repaired_records) * 100, 1)}%)")
    print(f"Canonical 8-Key Plan & Sync:    {structure_fixed}")
    print(f"Remaining Unfixable:             {unfixable}")

    # Backup original
    if args.output == input_path:
        backup_path = args.output.with_suffix(args.output.suffix + ".bak")
        if not backup_path.exists():
            shutil.copy2(args.output, backup_path)
            print(f"[✓] Original backed up to: {backup_path}")

    # Write repaired dataset
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for rec in repaired_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"[✓] Repaired dataset saved to: {args.output}")
    print("=" * 70)

if __name__ == "__main__":
    main()
