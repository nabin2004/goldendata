#!/usr/bin/env python3
"""Validate one returned 10-slide ChatUI completion.

Usage:
    python scripts/validate_slide10.py path/to/completion.txt
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import yaml


SLIDE_CLASSES = [
    "Slide01_Title",
    "Slide02_Motivation",
    "Slide03_Prerequisites",
    "Slide04_CoreIdea",
    "Slide05_Construction",
    "Slide06_Formal",
    "Slide07_Example",
    "Slide08_Camera",
    "Slide09_Pitfalls",
    "Slide10_Recap",
]
BLOCKS = re.compile(r"\A\s*<Plan>\s*(.*?)\s*</Plan>\s*```python\s*(.*?)\s*```\s*<End>\s*(.*?)\s*</End>\s*\Z", re.S)
BOOKMARK = re.compile(r"<bookmark\s+mark=['\"]([^'\"]+)['\"]\s*/>")
WAIT = re.compile(r"wait_until_bookmark\(\s*['\"]([^'\"]+)['\"]\s*\)")


def validate(text: str) -> list[str]:
    errors: list[str] = []
    match = BLOCKS.match(text)
    if not match:
        return ["STRUCTURE: expected Plan, python, and End blocks with no surrounding prose"]
    plan_text, code, end_text = match.groups()
    try:
        plan = yaml.safe_load(plan_text)
        end = yaml.safe_load(end_text)
    except yaml.YAMLError as exc:
        return [f"YAML: {exc}"]

    if not isinstance(plan, dict) or plan.get("slide_count") != 10:
        errors.append("PLAN: slide_count must be 10")
    slides = plan.get("slides", []) if isinstance(plan, dict) else []
    plan_classes = [slide.get("class") for slide in slides] if isinstance(slides, list) else []
    if plan_classes != SLIDE_CLASSES:
        errors.append("PLAN: slide classes do not match the fixed role order")

    if not isinstance(end, dict) or end.get("slide_count") != 10:
        errors.append("END: slide_count must be 10")
    if isinstance(end, dict) and end.get("slide_order") != SLIDE_CLASSES:
        errors.append("END: slide_order does not match the fixed role order")

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return errors + [f"PYTHON: {exc.msg} at line {exc.lineno}"]

    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    if [name for name in SLIDE_CLASSES if name in classes] != SLIDE_CLASSES:
        errors.append("PYTHON: exactly the ten required slide classes are not present")
    for name in SLIDE_CLASSES:
        node = classes.get(name)
        if node is None:
            continue
        bases = {ast.unparse(base) for base in node.bases}
        if "SlideBase" not in bases:
            errors.append(f"PYTHON: {name} must inherit SlideBase")
        source = ast.get_source_segment(code, node) or ""
        if "self.voiceover(" not in source:
            errors.append(f"VOICEOVER: {name} has no voiceover block")
        if "self.clear_slide()" not in source:
            errors.append(f"CLEAR: {name} does not end with clear_slide()")

    narration_marks = set(BOOKMARK.findall(code))
    wait_marks = set(WAIT.findall(code))
    if narration_marks != wait_marks:
        errors.append("BOOKMARKS: narration and wait_until_bookmark sets differ")
    return errors


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    errors = validate(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("slide10 completion: OK")


if __name__ == "__main__":
    main()