#!/usr/bin/env python3
"""Transform batch3_500.jsonl (r00200-r00699) samples to canonical Manim-AOS format."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Read already processed IDs
processed_ids = set()
for f in ['data/canonical/candidates.jsonl', 'data/canonical/candidates_batch2.jsonl', 'data/canonical/candidates_batch3.jsonl']:
    p = ROOT / f
    if p.exists():
        with open(p) as f:
            for line in f:
                rec = json.loads(line)
                processed_ids.add(rec["id"])

print(f"Already processed: {len(processed_ids)} samples")

# Load environment
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import httpx

def call_llm(prompt: str, model: str = None) -> str:
    model = model or os.environ.get("TRANSFORM_MODEL", "auto/best-coding")
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

def api_notes(code: str, limit=12) -> str:
    import re
    names = sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9]+)\(", code)))[:limit]
    if not names:
        return "No Manim classes detected."
    return "\n".join([f"{n}: used in code" for n in names])

def load_transform_prompt() -> str:
    return (ROOT / "prompts/transform.md").read_text()

def transform_sample(instruction: str, legacy_code: str, template: str, retries=3) -> str | None:
    prompt = template.format(
        instruction=instruction,
        legacy_code=legacy_code,
        api_notes=api_notes(legacy_code)
    )
    
    for attempt in range(retries):
        try:
            text = call_llm(prompt).strip()
            if "<Plan>" in text and "```python" in text:
                return text
            print(f"  Attempt {attempt+1} failed", file=sys.stderr)
        except Exception as e:
            print(f"  Attempt {attempt+1} error: {e}", file=sys.stderr)
    return None

def main():
    input_file = ROOT / "data/triage/batch3_500.jsonl"
    output_file = ROOT / "data/canonical/candidates_batch3.jsonl"
    
    samples = [json.loads(l) for l in open(input_file)]
    template = load_transform_prompt()
    
    # Filter to unprocessed samples
    remaining = [s for s in samples if s.get("id") not in processed_ids]
    print(f"Processing {len(remaining)} of {len(samples)} samples")
    
    for i, sample in enumerate(remaining):
        sample_id = sample.get("id", f"r{i:05d}")
        instruction = sample.get("instruction", "")
        code = sample.get("code", "") or sample.get("output", "")
        
        print(f"[{i+1}/{len(remaining)}] {sample_id}: ", end="", flush=True)
        
        if not code.strip():
            print("SKIP")
            continue
            
        result = transform_sample(instruction, code, template)
        
        if result:
            print("OK")
            with open(output_file, "a") as f:
                f.write(json.dumps({
                    "id": sample_id,
                    "instruction": instruction,
                    "response": result
                }) + "\n")
        else:
            print("FAILED")
        
        if (i + 1) % 50 == 0:
            print(f"Progress: {i+1}/{len(remaining)} completed")
    
    print("Done!")

if __name__ == "__main__":
    main()