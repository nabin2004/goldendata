# Dataset Workflow Decision Progress

## 2026-10-01

### Request
Run Docker renders with 10 renders active at a time and prepare the Manim-AOS dataset workflow.

### Decision 1: Use the verifier concurrency control
- The controlling script is `verify_dataset_docker.py`.
- It exposes `--concurrency`; the default is 100, but `--concurrency 10` gives exactly ten simultaneous Docker render jobs.
- I will use the existing verifier rather than introduce a second batching implementation.

### Decision 2: Preserve verification artifacts
- I will not use `--clean` for the render run unless explicitly needed, so valid completed videos remain reusable.
- Full-render cache validity must be based on `video.mp4`, not only `scene.py`.

### Preflight result
- Docker check from Windows PowerShell failed:
  `request returned 500 Internal Server Error ... dockerDesktopLinuxEngine ... /info`
- Existing `data/verification_run/passed` directories: 0.
- Existing `data/verification_run/failed` directories: 0.

### Next step
Attempt the full verifier with `--concurrency 10`. Record the exact result and any Docker/Desktop blocker before deciding whether a WSL-side Docker start or Docker Desktop restart is required.

### Decision 3: Render one sample at a time
- The requested execution mode is now strictly serial.
- I will use `--concurrency 1 --limit 1`, preserving existing artifacts and avoiding `--clean`.
- This first run is a connectivity and renderer probe; it does not claim the full dataset is complete.

### End-to-end attempt: 2026-10-01
- Command requested: `uv run python -m manim_aos_data.cli render --limit 10`.
- Result: failed before pipeline startup with `uv` error `failed to remove directory .venv/bin (os error 145)`.
- Diagnosis: the command was executed by Windows `uv.exe` against the WSL UNC workspace; `.venv/bin/python3.13` is a WSL symlink that Windows cannot safely replace.
- Decision: execute the command from inside Ubuntu using Linux `uv`, preserving the existing virtual environment and dataset artifacts.
- WSL-native result: `.venv` was recreated successfully, but `manim_aos_data.cli` was not importable.
- Diagnosis: `pyproject.toml` declared setuptools package discovery but no explicit PEP 517 build backend, so `uv run` installed dependencies without installing the local project.
- Decision: add the minimal setuptools build-system declaration; retain the `src/` layout and existing entry point.
- Ten-sample render result: all ten entered sequential processing but failed during dry-run.
- Failure split: most samples reported `FileNotFoundError: 'latex'`; one sample reached Voiceover and reported the Whisper transcription-model prerequisite.
- Diagnosis: `configs/pipeline.yaml` defaulted to `backend: local`, although the documented workflow and `docker/Dockerfile.render` are the supported headless render path.
- Decision: make Docker the default render backend; retain `RENDER_BACKEND` as an explicit override for local debugging.
- Docker build result: the first rebuild was canceled while resolving the very large CUDA dependency set pulled by `openai-whisper`.
- Diagnosis: the render hook already has a deterministic fallback that removes transcription kwargs when Whisper is unavailable; installing Whisper in the image is unnecessary for this headless render path and causes excessive image size/build time.
- Decision: remove `openai-whisper` from the render image, retain `GTTSService(transcription_model="base")` in dataset code, and rely on the existing non-interactive fallback during rendering.
- Re-run result: Docker was selected correctly, but the container itself reported `FileNotFoundError: 'latex'`; the Manim base image does not ship the LaTeX executable.
- Decision: install the documented TeX Live runtime packages in `Dockerfile.render` before retrying the render.
- TeX image build result: the expanded TeX package layer was canceled during export before updating the image tag.
- Decision: reduce the image to `texlive-latex-base` and `texlive-latex-extra`, the core bundles needed by the dataset's MathTex/Tex usage, to keep the build within the available Docker execution window.
- Image validation: `/usr/local/texlive/bin/x86_64-linux/latex` exists, but the real `manim` entrypoint still reported `latex` missing.
- Diagnosis: TeX Live's executable directory was not on the runtime `PATH` used by the image entrypoint.
- Decision: export the TeX Live bin directory in `Dockerfile.render` and rebuild before the next end-to-end probe.
