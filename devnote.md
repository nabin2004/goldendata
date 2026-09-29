# devnote.md: running in Ubuntu/WSL2

Run the complete Python pipeline inside Ubuntu/WSL2. Keep the repository in the WSL filesystem (`/home/nabin/THEGOLDENDATASET`) and use Docker for isolated Manim rendering. Docker Desktop's WSL2 backend is supported; native Ubuntu rendering is also available after the system packages below are installed.

## 1. Prerequisites
```bash
sudo apt update
sudo apt install -y build-essential pkg-config libcairo2-dev libpango1.0-dev ffmpeg sox libsox-fmt-all
```

Check: `git --version`, `python3 --version`, `docker version`, and `make --version`. Python 3.11+ is supported; this workspace is configured with Python 3.13. Docker Desktop must have the WSL2 engine enabled. OpenCode is optional: install Node.js first, then run `npm i -g opencode-ai`.

## 2. Set up the Python side (Ubuntu, repo root)
```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
test -e .env || cp .env.example .env
.venv/bin/python scripts/docs/build_docs_index.py
PYTHONPATH=src .venv/bin/python -m pytest -q
```
If `uv` is not installed, use `python3 -m venv .venv` and `.venv/bin/pip install -e '.[dev]'`. The Makefile is the primary task runner in Ubuntu: `make setup`, `make test`, `make docker-build`, and `make docker-render`. Activate the environment with `source .venv/bin/activate` for interactive work.

## 3. Docker rendering
Build once (pin `MANIM_TAG` in `.env` to a `vX.Y.Z` tag matching Manim 0.19; check `docker run --rm manimcommunity/manim:stable manim --version`):
```bash
docker compose build render
```
Tags of `manimcommunity/manim`: `latest` (main branch), `stable` (latest release), `vX.Y.Z` (a specific release).

Point the pipeline at Docker and render:
```powershell
RENDER_BACKEND=docker .venv/bin/python -m manim_aos_data.cli render
```
Manual one-off render of a scene folder (throwaway container):
```bash
docker run --rm -it -v "$PWD/data/rendered/r00001:/manim" manim-aos-render manim -ql scene.py DerivativeScene
```
Named, modifiable container (for installing TeX packages with `tlmgr`):
```bash
docker run -it --name my-manim-container -v "$PWD/data/rendered/_scratch:/manim" manim-aos-render bash
docker start my-manim-container
docker exec -it my-manim-container manim -ql test_scenes.py CircleToSquare
```
JupyterLab: `docker compose --profile lab up lab`, then open the URL printed in the terminal (port 8888).

Docker limits: `-p` (preview) and `-f` (open output) do not work inside containers. The image has a minimal TeX Live: if a scene uses
`TexTemplateLibrary.ctex`, run `tlmgr install ctex` in the container (or uncomment that line in `docker/Dockerfile.render`).

## 4. Narration with Docker
- For zero-config cloud narration, set `TTS_SERVICE=GTTSService` in `.env`. In a scene, use `from manim_voiceover.services.gtts import GTTSService` and call `self.set_speech_service(GTTSService(lang="en"))`.
- The render image installs `gTTS`; rendering requires network access to Google Translate.
- Legacy `AOSSpeechService` scenes are no longer supported in this pipeline. If you need local/offline TTS, use `pyttsx3` service instead.
- The SPEC uses `from manim_voiceover.services.gtts import GTTSService`; call `self.set_speech_service(GTTSService())` first in `construct()`.

## 5. Typical run
```bash
python -m manim_aos_data.cli ingest --repo nabin2004/manim-aos-5k400
python -m manim_aos_data.cli triage
python -m manim_aos_data.cli transform      # needs LLM_* keys in .env
python -m manim_aos_data.cli validate
RENDER_BACKEND=docker python -m manim_aos_data.cli render
python -m manim_aos_data.cli omni
python -m manim_aos_data.cli package
```
Agents: run `opencode` in the repo root; it reads `AGENTS.md` and `.claude/skills/`.

## 6. Troubleshooting
| Symptom | Fix |
|---|---|
| `docker: error during connect` | Start Docker Desktop and wait for the engine to be ready |
| `SoX could not be found` | Native: install SoX and add to PATH. Docker: rebuild the image (`docker compose build render --no-cache`) |
| LaTeX / `standalone.cls` errors | Fix the image or MiKTeX install; do not edit scene code |
| Volume mount empty or "drive not shared" | Use a path on a drive Docker Desktop can access; prefer the WSL filesystem |
| Import error for `GTTSService` | Run `pip install "manim-voiceover[gtts]"` |
| Narration times out | Check internet access for Google Translate API |
| CRLF errors in shell scripts or Dockerfile | `.gitattributes` forces LF; re-clone or run `git add --renormalize .` |
| Long path errors | `git config core.longpaths true` and keep the repo near the drive root |
