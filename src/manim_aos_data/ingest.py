from pathlib import Path
import json, re
from datasets import load_dataset

def extract_code_from_message(content: str) -> str | None:
    """Extract python code from markdown blocks."""
    if not isinstance(content, str):
        return None
    match = re.search(r"```python\n(.*?)\n```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def ingest(repo: str, out: Path, split="train"):
    out.mkdir(parents=True, exist_ok=True)
    ds = load_dataset(repo, split=split)
    
    with open(out / "raw.jsonl", "w") as f:
        for i, row in enumerate(ds):
            # Extract instruction from user message
            instruction = ""
            for msg in row.get("messages", []):
                if msg.get("role") == "user":
                    instruction = msg.get("content", "")
                    break
            
            # Extract code from assistant message
            code = ""
            for msg in row.get("messages", []):
                if msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    code = extract_code_from_message(content) or ""
                    break
            
            # Check if code uses VoiceoverScene
            uses_voiceover = "VoiceoverScene" in code
            has_manimlib = bool(re.search(r"manimlib", code))
            
            output = {
                "id": f"r{i:05d}",
                "instruction": instruction,
                "code": code,
                "has_voiceover": uses_voiceover,
                "has_manimlib": has_manimlib,
                "metadata": row.get("metadata", {}),
                "messages": row.get("messages", [])
            }
            f.write(json.dumps(output, default=str) + "\n")
    
    return len(ds)
