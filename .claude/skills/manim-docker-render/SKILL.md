---
name: manim-docker-render
description: Render Manim scenes headlessly in Docker (manimcommunity/manim plus sox and manim-voiceover) for the dataset pipeline, including on Windows. Use when running stage 4, debugging render failures, or when local LaTeX/SoX/Cairo setup is missing.
---
# Docker rendering

Image: `docker/Dockerfile.render` (built on `manimcommunity/manim`, adds sox and manim-voiceover). Build: `docker compose build render`.
Select the backend: `RENDER_BACKEND=docker` (or `render.backend` in `configs/pipeline.yaml`), then `python -m manim_aos_data.cli render`.

Facts from the Manim docs
- Tags: `latest` (main branch), `stable` (latest release), `vX.Y.Z`. Pin the tag that matches `manim>=0.19,<0.20`.
- `-p` (preview) and `-f` (show file) are not supported inside Docker.
- Minimal TeX Live: `ctex` is absent; `tlmgr install ctex` if a scene uses `TexTemplateLibrary.ctex`.
- Linux: pass `--user "$(id -u):$(id -g)"` to avoid root-owned output files.

Pipeline specifics
- The container reaches the host TTS service at `host.docker.internal` (localhost is rewritten automatically).
- Mount the AOS monorepo with `AOS_REPO` and set `AOS_PYTHONPATH` so `AOSSpeechService` imports.
- SoX errors or LaTeX errors are host/image problems: fix the image, do not change scene code.
Windows steps: see `devnote.md`.
