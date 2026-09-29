"""Stage 2: legacy -> canonical via an LLM (OpenCode / OmniRoute OpenAI-compatible endpoint)."""
import json, subprocess, sys
from pathlib import Path
from .repair import call_llm
from .sample import parse_response

def api_notes(code: str, limit=12) -> str:
    """Retrieve signatures for every Manim name used, from the installed package."""
    import re
    names = sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9]+)\(", code)))[:limit]
    out = []
    for n in names:
        p = subprocess.run([sys.executable, "scripts/docs/api_lookup.py", n], capture_output=True, text=True)
        out.append(p.stdout.splitlines()[0] if p.returncode == 0 else f"{n}: NOT FOUND (do not use)")
    return "\n".join(out)

def transform(instruction: str, legacy: str, template: str, retries=3) -> str | None:
    prompt = template.format(instruction=instruction, legacy_code=legacy, api_notes=api_notes(legacy))
    for _ in range(retries):
        text = call_llm(prompt, "TRANSFORM_MODEL").strip()
        if not parse_response(text).errors:
            return text
    return None
