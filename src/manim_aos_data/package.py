"""Stage 6: SFT + DPO jsonl, 80/20 split by id hash, held-out eval."""
import hashlib, json
from pathlib import Path

def _bucket(i: str) -> float:
    return int(hashlib.sha1(i.encode()).hexdigest(), 16) % 1000 / 1000

def build(canonical: list[dict], repairs: list[dict], out: Path):
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "sft.jsonl", "w") as f:
        for r in canonical:
            f.write(json.dumps({"messages": [
                {"role": "user", "content": r["instruction"]},
                {"role": "assistant", "content": f"<Plan>\n{r['plan_text']}\n</Plan>\n```python\n{r['code']}\n```"}]}) + "\n")
    with open(out / "dpo.jsonl", "w") as f:
        for r in repairs:
            f.write(json.dumps({"prompt": r["instruction"], "chosen": r["v2_code"], "rejected": r["v1_code"],
                                "signal": r["signal"], "diff_lines": r["diff_lines"]}) + "\n")
