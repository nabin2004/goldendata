# manim-aos-dataset

Pipeline to turn `nabin2004/manim-aos-5k400` into a high-quality Manim CE v0.19+ SFT / DPO dataset
with `<Plan>` blocks, verified voiceover bookmarks, robust layout and repair trajectories.

```
raw → [1 AST triage] → [2 OpenCode transform] → [3 linter] → [4 headless render + TTS] → [5 Omni QC] → SFT + DPO
```

## Quick start
```bash
cp .env.example .env            # fill in keys
make setup
make docs-index                 # builds local Manim / manim-voiceover docs index
python -m manim_aos_data.cli ingest --repo nabin2004/manim-aos-5k400
make triage transform validate render omni package
```
See `AGENTS.md` for agent rules, `docs/SPEC.md` for the sample contract, `docs/DOCS_LOOKUP.md` for querying library docs.
