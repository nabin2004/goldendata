# Pipeline

| # | Stage | Module | Input → Output | Reject codes |
|---|---|---|---|---|
| 1 | Ingest + AST triage | `ingest.py`, `ast_triage.py` | `data/raw` → `data/triage` | `SYNTAX_ERROR`, `NO_SCENE`, `MANIMLIB` |
| 2 | OpenCode canonical transform | `transform.py`, `prompts/transform.md` | triage → `data/canonical` (candidate) | `NOT_TWO_BLOCK`, `PLAN_SCHEMA` |
| 3 | Deterministic linter | `linter/*` | candidate → pass/fail + auto-fixes | see `LINTER_RULES.md` |
| 4 | Headless render + TTS | `render.py` | code → mp4, audio, timing json | `RENDER_FAIL`, `TTS_FAIL`, `TIMEOUT` |
| 5 | Omni QC + repair | `omni_qc.py`, `repair.py` | mp4 + frames → verdict, repair traces | `OVERLAP`, `CLIPPED`, `AV_DRIFT` |
| 6 | Package | `package.py` | passing + repairs → SFT/DPO jsonl | — |

Loop: stages 3–5 failures go to `repair.py` (max `llm.max_repair_rounds`); the V1→diagnosis→fix→V2 trace is stored in `data/repairs/`.

## Data records
`data/canonical/*.jsonl`: `{id, instruction, plan, code, source_id, lint, render, omni}`
`data/repairs/*.jsonl`: `{id, v1_code, diagnosis, fix_summary, v2_code, diff_lines, signal: lint|runtime|vision}`
`data/packaged/sft.jsonl`: chat format `[{role:user},{role:assistant}]`
`data/packaged/dpo.jsonl`: `{prompt, chosen, rejected}` (rejected = failing V1, chosen = verified V2)
