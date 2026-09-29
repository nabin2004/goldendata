"""Parse a model response into (plan dict, code) and enforce the two-block contract."""
import re
from dataclasses import dataclass

PLAN_KEYS = ["goal", "skills", "layout", "camera", "dynamics", "math", "narration", "validate"]
_RESP = re.compile(r"\A\s*<Plan>\n?(.*?)\n?</Plan>\s*```python\n(.*?)\n```\s*\Z", re.S)

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
    plan_txt, code = m.groups()
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
    return Sample(plan, code, errs)

def plan_bookmarks(plan: dict) -> set:
    return set(re.findall(r"<bookmark mark=['\"](.*?)['\"]\s*/>", plan.get("narration", "")))
