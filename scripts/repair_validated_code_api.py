#!/usr/bin/env python3
"""Repair known Manim 0.19 Code constructor kwargs in validated samples."""

import json
import re
import shutil
import sys
from pathlib import Path


def repair_code(code: str) -> tuple[str, bool]:
    lines = code.splitlines()
    repaired: list[str] = []
    in_code_call = False
    changed = False
    for line in lines:
        if re.search(r"\bCode\s*\(", line):
            in_code_call = True
        if in_code_call and re.match(r"^\s*code\s*=", line):
            line = re.sub(r"^(\s*)code\s*=", r"\1code_string=", line)
            changed = True
        if in_code_call and re.match(r"^\s*font_size\s*=", line):
            changed = True
            continue
        if in_code_call and re.match(r"^\s*style\s*=", line):
            line = line.replace("style=", "formatter_style=", 1)
            changed = True
        repaired.append(line)
        if in_code_call and re.match(r"^\s*\)\s*,?\s*$", line):
            in_code_call = False
    return "\n".join(repaired), changed


def repair_response(response: str) -> tuple[str, bool]:
    match = re.search(r"```python\s*(.*?)\s*```", response, re.DOTALL)
    if not match:
        return response, False
    code, changed = repair_code(match.group(1))
    if not changed:
        return response, False
    return response[:match.start(1)] + code + response[match.end(1):], True


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/canonical/validated.jsonl")
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    records = []
    changed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        response, was_changed = repair_response(record.get("response", ""))
        if was_changed:
            record["response"] = response
            changed += 1
        records.append(json.dumps(record, ensure_ascii=False))
    path.write_text("\n".join(records) + "\n", encoding="utf-8")
    print(f"Repaired {changed} validated sample records; backup: {backup}")


if __name__ == "__main__":
    main()
