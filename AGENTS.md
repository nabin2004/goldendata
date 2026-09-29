# AGENTS.md — Manim-AOS dataset refinement

Read this first. It is the operating manual for any coding agent (OpenCode, Claude Code, etc.) working in this repo.

## Mission
Refine `nabin2004/manim-aos-5k400` (5k+ Manim examples) into a gold SFT set plus repair/DPO traces.
Targets: pass@1 ≈ 100%, zero hallucinated APIs, Manim CE v0.19+ only, exact narration↔bookmark sync,
frame-relative layout. Full spec: `docs/SPEC.md`. Pipeline: `docs/ARCHITECTURE.md`.

## Golden rules
1. **Never guess an API. Look it up** (see "Docs lookup" below) before writing or keeping any Manim / manim-voiceover call.
2. **Never edit `data/raw/`.** It is read-only input. All outputs go to a later stage directory.
3. **Deterministic first, LLM second.** If a check or rewrite can be done with AST/regex/`inspect`, do it in code (`src/manim_aos_data/linter/`), not with an LLM.
4. **Minimal diffs.** Fix what is wrong; do not restyle working code. Repair traces are scored on minimal diff.
5. **Every sample must pass the linter and a headless render before entering `data/canonical/`.**
6. Keep the two-block contract: exactly one `<Plan>…</Plan>` then exactly one ```python block, nothing else.
7. Log every rejection with a reason code in `logs/rejections.jsonl`. Never silently drop samples.

## Repo map
| Path | Purpose |
|---|---|
| `src/manim_aos_data/` | Pipeline code (ingest, ast_triage, transform, linter, render, omni_qc, repair, package, cli) |
| `src/manim_aos_data/linter/` | One module per lint check (see `docs/LINTER_RULES.md`) |
| `configs/` | `pipeline.yaml`, banned kwargs, deprecated map, Plan JSON schema |
| `prompts/` | LLM prompt templates (transform, repair, omni_qc) |
| `.opencode/agent/` | OpenCode subagents (transformer, repairer, omni-qc, docs-researcher) |
| `.claude/skills/` | Agent skills: manim-voiceover-aos, manim-docs-lookup, manim-aos-canonical-sample, dataset-lint-repair, manim-docker-render |
| `docker/`, `docker-compose.yml` | Render image (manimcommunity/manim + sox + manim-voiceover) |
| `devnote.md` | Windows / Docker run guide |
| `scripts/docs/` | Build/query local docs index (Manim, manim-voiceover, NumPy/SciPy/SymPy) |
| `data/` | `raw → triage → canonical → rendered → repairs → packaged` |
| `docs_cache/` | Generated docs index (gitignored) |
| `tests/` | pytest suite; `tests/fixtures/` holds good/bad samples |

## Commands
```bash
make setup            # venv + deps + docs index
make docs-index       # (re)build local docs index for the pinned Manim version
make lint-sample F=path/to/sample.json
make triage           # stage 1
make transform        # stage 2 (LLM via OpenCode / OmniRoute)
make validate         # stage 3
make render           # stage 4 (manim -ql + GTTSService)
make omni             # stage 5
make package          # SFT + DPO jsonl
make test
make docker-build     # build the render image
make docker-render    # stage 4 inside Docker (RENDER_BACKEND=docker)
```
Skills live in `.claude/skills/` (OpenCode and Claude Code both read this path; if your OpenCode version does not, copy them to `.opencode/skill/`). Load the matching skill before docs lookups, sample writing, repairs and Docker renders.

## Docs lookup (mandatory before using an API)
Sources of truth, in order:
1. **Installed-version introspection** (authoritative for the pinned Manim):
   `python scripts/docs/api_lookup.py Circle` → signature, docstring, MRO, accepted kwargs.
   Use `--methods Circle` to list public methods.
2. **Local docs search** (Sphinx inventory + cached pages):
   `python scripts/docs/query_docs.py "always_redraw" --project manim`
   `python scripts/docs/query_docs.py "wait_until_bookmark" --project manim_voiceover`
   Add `--fetch` to download and print the matching doc page section.
3. **Context7 MCP** (configured in `opencode.json`): ask for library docs by name, e.g. `manim`, `manim-voiceover`, `scipy`, `sympy`.
4. **Web**: https://docs.manim.community/en/stable/ and https://voiceover.manim.community/
   - Reference manual: `.../reference.html`; per-object pages: `.../reference/manim.<module>.<Class>.html`
   - Sphinx inventory (machine readable): `.../en/stable/objects.inv`

If the sources disagree, **installed-version introspection wins**. If an API is not found anywhere, it is a hallucination: remove or replace it.
`GTTSService` is from `manim_voiceover.services.gtts` (requires `pip install "manim-voiceover[gtts]"`); zero setup, uses Google Translate API.

## Definition of done (per sample)
- [ ] Two-block contract holds; Plan has the 8 keys in fixed order, one line each
- [ ] Bookmark set in `narration` == set in `wait_until_bookmark(...)` calls, and each call is inside its `with self.voiceover` block
- [ ] All kwargs valid per `inspect.signature` (or documented `**kwargs` pass-through checked against parent class)
- [ ] No deprecated / banned patterns (`configs/deprecated_map.yaml`)
- [ ] Raw LaTeX strings, no unicode sub/superscripts
- [ ] `fit_in_frame` defined and used; layout uses relative positioning; `MARGIN = 0.5`
- [ ] Camera moves paired with `save_state()` + `Restore`
- [ ] `manim -ql` render succeeds; audio generated; Omni QC has no overlap/clipping flags

## Style for agent edits
- Python 3.11, type hints, `ruff` + `pytest`. Small pure functions. No network calls inside linter modules.
- Prompts live in `prompts/`, not inline in code.
- When unsure, open a rejection with a reason code rather than inventing a fix.
