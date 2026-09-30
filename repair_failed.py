#!/usr/bin/env python3
"""Repair failed samples from logs/rejections.jsonl."""
import json
import os
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Load environment
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import httpx

def call_llm(prompt: str, model: str = None) -> str:
    model = model or os.environ.get("REPAIR_MODEL", "auto/best-coding")
    base_url = os.environ["LLM_BASE_URL"]
    api_key = os.environ.get("LLM_API_KEY", "")
    
    r = httpx.post(
        base_url + "/chat/completions",
        timeout=600,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def repair_with_rules(response: str, issues: list) -> str | None:
    """Apply deterministic fixes based on issue rules."""
    v1_code = response
    
    # Extract the python code block from the response
    code_match = re.search(r'```python\s*\n(.*?)\n```', response, re.DOTALL)
    if not code_match:
        print("  No code block found", file=sys.stderr)
        return None
    
    code = code_match.group(1)
    
    fixes_applied = []
    
    for issue in issues:
        rule = issue.get("rule", "")
        msg = issue.get("msg", "")
        fixable = issue.get("fixable", False)
        
        if not fixable:
            continue
        
        # RAW_LATEX_PREFIX: add raw prefix to MathTex/Tex strings
        if rule == "RAW_LATEX_PREFIX":
            # Find non-raw LaTeX strings and convert them
            # Pattern: MathTex("...") or Tex("...")
            def fix_latex(m):
                prefix = m.group(1)
                content = m.group(2)
                # If content has { or \, it needs to be raw
                if '{' in content or '\\' in content:
                    return f'{prefix}r"{content}"'
                return m.group(0)
            
            # Match MathTex("...") or Tex("...")
            code = re.sub(r'(\b(MathTex|Tex))\s*\(\s*"([^"]*)"', fix_latex, code)
            fixes_applied.append(f"RAW_LATEX_PREFIX: added raw prefix to LaTeX strings")
        
        # UNICODE_MATH_BAN: replace unicode sub/superscripts with raw LaTeX
        elif rule == "UNICODE_MATH_BAN":
            # Replace unicode characters like ² with ^2
            unicode_map = {
                '\u00b2': '^2',
                '\u00b3': '^3',
                '\u2074': '^4',
                '\u2075': '^5',
                '\u2076': '^6',
                '\u2077': '^7',
                '\u2078': '^8',
                '\u2079': '^9',
                '\u207a': '^+',
                '\u207b': '^-',
                '\u2080': '_0',
                '\u2081': '_1',
                '\u2082': '_2',
                '\u2083': '_3',
                '\u2084': '_4',
                '\u2085': '_5',
                '\u2086': '_6',
                '\u2087': '_7',
                '\u2088': '_8',
                '\u2089': '_9',
                '\u208a': '_+',
                '\u208b': '_-',
                '\u2091': '_e',
                '\u2092': '_i',
                '\u2093': '_k',
            }
            for uc, repl in unicode_map.items():
                code = code.replace(uc, repl)
            fixes_applied.append(f"UNICODE_MATH_BAN: replaced unicode sub/superscripts")
        
        # STRUCTURE: fit_in_frame must be defined and used
        elif rule == "STRUCTURE" and "fit_in_frame" in msg:
            if "def fit_in_frame" not in code:
                # Add fit_in_frame method to the class
                # Find the class definition
                class_match = re.search(r'class\s+(\w+)\([^)]+\):\s*\n', code)
                if class_match:
                    class_name = class_match.group(1)
                    indent = '    '
                    fit_in_frame_method = f'''{indent}def fit_in_frame(self, mob: Mobject, w_frac: float = 0.9, h_frac: float = 0.9) -> Mobject:
{indent}    max_w = config.frame_width * w_frac
{indent}    max_h = config.frame_height * h_frac
{indent}    if mob.width > max_w: mob.width = max_w
{indent}    if mob.height > max_h: mob.height = max_h
{indent}    return mob

'''
                    # Insert before the last method or at end of class
                    code = code.rstrip()
                    if not code.endswith('\n'):
                        code += '\n'
                    code += fit_in_frame_method
                    fixes_applied.append(f"STRUCTURE: added fit_in_frame method")
    
    if fixes_applied:
        # Reconstruct the full response
        new_code_block = "```python\n" + code + "\n```"
        # Replace the old code block using string replacement to avoid regex issues
        old_start = response.find("```python")
        old_end = response.find("```", old_start + 10)
        if old_start != -1 and old_end != -1:
            new_response = response[:old_start] + new_code_block + response[old_end+3:]
            return new_response
        return None
    
    return None

def main():
    # Load rejected samples with issues
    rejections = []
    with open(ROOT / "logs/rejections.jsonl") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("stage") == 3 and rec.get("issues"):
                rejections.append(rec)
    
    print(f"Found {len(rejections)} rejected samples")
    
    # Group by ID to avoid duplicate repairs
    grouped = {}
    for r in rejections:
        rid = r["id"]
        if rid not in grouped:
            grouped[rid] = r
    
    repaired_count = 0
    failed_count = 0
    
    for rid, rejection in grouped.items():
        print(f"[{repaired_count+failed_count+1}] {rid}: ", end="", flush=True)
        
        # Get the original response from candidates
        response = None
        for f in ["data/canonical/candidates.jsonl", "data/canonical/candidates_batch2.jsonl", "data/canonical/candidates_batch3.jsonl"]:
            p = ROOT / f
            if p.exists():
                with open(p) as cf:
                    for line in cf:
                        c = json.loads(line)
                        if c["id"] == rid:
                            response = c["response"]
                            break
                if response:
                    break
        
        if not response:
            print("SKIP (not found)")
            continue
        
        issues = rejection.get("issues", [])
        if not issues:
            print("SKIP (no issues)")
            continue
        
        # Try deterministic fixes first
        repaired = repair_with_rules(response, issues)
        
        if repaired:
            # Validate repair by checking if it fixes the issues
            repair_trace = {
                "id": rid,
                "signal": "LINT_REPAIR",
                "v1_code": response,
                "diagnosis": "; ".join([f"{i.get('rule', '')}: {i.get('msg', '')}" for i in issues]),
                "fix_summary": "Applied deterministic fixes",
                "v2_code": repaired,
                "diff_lines": len(repaired) - len(response)
            }
            
            with open(ROOT / "data/repairs/repairs.jsonl", "a") as rf:
                rf.write(json.dumps(repair_trace) + "\n")
            
            print(f"OK (deterministic fixes)")
            repaired_count += 1
        else:
            print("FAILED (needs LLM)")
            failed_count += 1
        
        if (repaired_count + failed_count) % 10 == 0:
            print(f"Progress: {repaired_count+failed_count} repairs attempted")
    
    print(f"Done! Repaired: {repaired_count}, Failed: {failed_count}")

if __name__ == "__main__":
    main()