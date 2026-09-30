"""Parse canonical model responses and validate the optional closing block."""
import re
from dataclasses import dataclass

PLAN_KEYS = ["goal", "skills", "layout", "camera", "dynamics", "math", "narration", "validate"]
END_KEYS = ["WhatWasBuilt", "WhatWasDemonstrated", "AnimationAndNarration", "ExpectedChecks"]
_RESP = re.compile(
    r"\A\s*<Plan>\n?(.*?)\n?</Plan>\s*```python\n(.*?)\n```"
    r"(?:\s*<End>\n?(.*?)\n?</End>)?\s*\Z",
    re.S,
)

@dataclass
class Sample:
    plan: dict
    code: str
    errors: list

def parse_response(text: str) -> Sample:
    errs = []
    m = _RESP.match(text)
    if not m:
        return Sample({}, "", ["NOT_TWO_BLOCK"])
    plan_txt, code, end_txt = m.groups()
    lines = [l for l in plan_txt.splitlines() if l.strip()]
    plan, order = {}, []
    for l in lines:
        k, sep, v = l.partition(":")
        if not sep or k.strip() not in PLAN_KEYS:
            errs.append(f"PLAN_BAD_LINE:{l[:40]}")
            continue
        plan[k.strip()] = v.strip(); order.append(k.strip())
    if order != PLAN_KEYS:
        errs.append("PLAN_KEYS_ORDER_OR_MISSING")
    if text.count("<Plan>") != 1 or text.count("```python") != 1:
        errs.append("NOT_TWO_BLOCK")
    if end_txt is not None:
        end, end_order = {}, []
        for key in END_KEYS:
            tag = re.search(rf"<{key}>(.*?)</{key}>", end_txt, re.S)
            if tag is None:
                errs.append(f"END_MISSING:{key}")
            else:
                end[key] = tag.group(1).strip()
                end_order.append(key)
        if end_order != END_KEYS or len(re.findall(r"</?[A-Za-z][^>]*>", end_txt)) != len(END_KEYS) * 2:
            errs.append("END_KEYS_ORDER_OR_MISSING")
    return Sample(plan, code, errs)

def plan_bookmarks(plan: dict) -> set:
    return set(re.findall(r"<bookmark mark=['\"](.*?)['\"]\s*/>", plan.get("narration", "")))
