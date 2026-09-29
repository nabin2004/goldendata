"""Build V1 -> diagnosis -> V2 traces. LLM call via any OpenAI-compatible endpoint."""
import difflib, json, os
import httpx

def call_llm(prompt: str, model_env="REPAIR_MODEL") -> str:
    r = httpx.post(os.environ["LLM_BASE_URL"] + "/chat/completions", timeout=600,
                   headers={"Authorization": "Bearer " + os.environ.get("LLM_API_KEY", "")},
                   json={"model": os.environ[model_env], "messages": [{"role": "user", "content": prompt}], "temperature": 0.2})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def diff_size(a: str, b: str) -> int:
    return sum(1 for l in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="") if l[:1] in "+-" and l[:3] not in ("+++", "---"))

def make_trace(v1: str, signal: str, diagnosis: str, template: str) -> dict:
    out = json.loads(call_llm(template.format(signal=signal, diagnosis=diagnosis, v1_code=v1)))
    return {"signal": signal, "v1_code": v1, "diagnosis": out["diagnosis"], "fix_summary": out["fix_summary"],
            "v2_code": out["v2_code"], "diff_lines": diff_size(v1, out["v2_code"])}
