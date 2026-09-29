#!/usr/bin/env python3
"""Transform first_100.jsonl samples to canonical Manim-AOS format."""
import json
import os
import sys
from pathlib import Path

# Load environment
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

import httpx

def call_llm(prompt: str, model: str = None) -> str:
    """Call OmniRoute LLM endpoint."""
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
    """Get API signatures from the codebase."""
    import re
    names = sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9]+)\(", code)))[:limit]
    if not names:
        return "No Manim classes detected."
    
    # Use a simple approach - just list the classes used
    return "\n".join([f"{n}: used in code (verify signature if uncertain)" for n in names])

def load_transform_prompt() -> str:
    """Load the transform prompt template."""
    return (ROOT / "prompts/transform.md").read_text()

def transform_sample(instruction: str, legacy_code: str, template: str, retries=3) -> str | None:
    """Transform a single sample to canonical format."""
    prompt = template.format(
        instruction=instruction,
        legacy_code=legacy_code,
        api_notes=api_notes(legacy_code)
    )
    
    for attempt in range(retries):
        try:
            text = call_llm(prompt).strip()
            # Basic validation - check for required blocks
            if "<Plan>" in text and "```python" in text:
                return text
            print(f"  Attempt {attempt+1} failed validation, retrying...", file=sys.stderr)
        except Exception as e:
            print(f"  Attempt {attempt+1} error: {e}", file=sys.stderr)
    
    return None

def main():
    input_file = ROOT / "data/triage/first_100.jsonl"
    output_file = ROOT / "data/canonical/candidates.jsonl"
    rejected_file = ROOT / "logs/rejections.jsonl"
    
    # Ensure output directories exist
    output_file.parent.mkdir(parents=True, exist_ok=True)
    rejected_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load samples
    samples = [json.loads(l) for l in open(input_file)]
    template = load_transform_prompt()
    
    print(f"Processing {len(samples)} samples...")
    
    for i, sample in enumerate(samples):
        sample_id = sample.get("id", f"r{i:05d}")
        instruction = sample.get("instruction", "")
        code = sample.get("code", "") or sample.get("output", "")
        
        print(f"[{i+1}/100] {sample_id}: ", end="", flush=True)
        
        if not code.strip():
            # No code to transform - skip or mark as rejected
            print("SKIP (no code)")
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
            with open(rejected_file, "a") as f:
                f.write(json.dumps({
                    "id": sample_id,
                    "stage": 2,
                    "reason": "TRANSFORM_FAILED"
                }) + "\n")
        
        # Progress indicator every 10
        if (i + 1) % 10 == 0:
            print(f"Progress: {i+1}/100 completed")
    
    print("Done!")

if __name__ == "__main__":
    main()