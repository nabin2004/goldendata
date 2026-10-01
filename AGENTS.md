# AGENTS.md

## Read this first
This repo builds and verifies a high-quality Manim Voiceover dataset for SFT and repair traces. The canonical docs are:

- [README.md](README.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/SPEC.md](docs/SPEC.md)
- [docs/DOCS_LOOKUP.md](docs/DOCS_LOOKUP.md)
- [docs/LINTER_RULES.md](docs/LINTER_RULES.md)

## Mission
Refine the raw dataset into validated, renderable examples that follow the strict two-block contract and exact narration/bookmark synchronization. The target is a clean gold set with minimal, evidence-driven repairs.

## Mandatory rules
1. Never guess a Manim or manim-voiceover API. Validate against the installed package and the local docs before keeping or writing code.
2. Do not edit [data/raw/](data/raw/). It is read-only input.
3. Prefer deterministic fixes in [src/manim_aos_data/](src/manim_aos_data/) and [src/manim_aos_data/linter/](src/manim_aos_data/linter/) over LLM-only rewrites.
4. Keep patches minimal. Fix the failing condition, not the surrounding style.
5. Every sample that enters canonical data must pass lint and a headless render.
6. Preserve the exact output contract: one `<Plan>...</Plan>` block followed by one Python code block.
7. Reject samples with a reason code instead of silently dropping them.

## Repo map
- [src/manim_aos_data/](src/manim_aos_data/) — pipeline code for triage, linting, render, QC, repair, and packaging
- [src/manim_aos_data/linter/](src/manim_aos_data/linter/) — per-rule lint checks
- [configs/](configs/) — pipeline and schema config
- [prompts/](prompts/) — generation and repair prompts
- [scripts/docs/](scripts/docs/) — local docs index and API lookup tools
- [data/](data/) — raw, triage, canonical, render, repair, and packaged outputs
- [tests/](tests/) — regression tests and fixtures

## Useful commands
```bash
make setup
make docs-index
make lint-sample F=path/to/sample.json
make triage
make transform
make validate
make render
make omni
make package
make test
```

## Docs lookup workflow
Use this order:
1. Installed package introspection (`python scripts/docs/api_lookup.py ...`)
2. Local Sphinx index search (`python scripts/docs/query_docs.py ...`)
3. Context7 / repo docs guidance if available
4. Web docs only as a last resort

If the sources disagree, the installed-version introspection is authoritative.

## Definition of done for a sample
- Two-block contract holds with the required plan keys in order
- Every narration bookmark matches a `wait_until_bookmark(...)` call in the same `with self.voiceover` block
- All kwargs are valid for the current package version
- No banned or deprecated patterns remain
- LaTeX is valid raw string content without unicode sub/superscripts
- Frame-relative layout and `fit_in_frame` usage are correct
- Camera movement is paired with `save_state()` / `Restore`
- A render completes successfully and passes QC

## Working style
- Python 3.11, typed helper functions, and small deterministic checks are preferred.
- Keep prompts in [prompts/](prompts/) instead of embedding them in code.
- When a fix is uncertain, reject with a reason code and keep the evidence trail.
