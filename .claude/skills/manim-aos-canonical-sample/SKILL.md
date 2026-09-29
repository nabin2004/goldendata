---
name: manim-aos-canonical-sample
description: Write or rewrite a Manim sample into the canonical Manim-AOS two-block format (one <Plan> with 8 keys, then one python block with VoiceoverScene, bookmarks, fit_in_frame and section comments). Use when creating, transforming or reviewing SFT dataset samples.
---
# Canonical Manim-AOS sample

Full contract: `docs/SPEC.md`. Reference sample: `tests/fixtures/good_derivative.txt`.

Checklist
- Output is exactly `<Plan>...</Plan>` then one ```python block. No prose outside.
- Plan keys in order, one line each: goal, skills, layout, camera, dynamics, math, narration, validate.
- Every `<bookmark mark='x'/>` in narration equals a `self.wait_until_bookmark("x")` inside the same `with self.voiceover(...)` block.
- `self.set_speech_service(GTTSService())` is the first statement of `construct()`.
- `fit_in_frame` defined and used; layout via next_to/to_edge/to_corner/arrange/align_to; MARGIN = 0.5.
- Section comments: `# [SETUP] # [LAYOUT] # [UPDATER] # [BEAT n | sync: label] # [CAMERA]`.
- One ValueTracker + always_redraw/DecimalNumber; never rebuild MathTex per frame.
- Camera: `save_state()` before, `Restore(self.camera.frame)` after; add MovingCameraScene only if the camera moves.
- Raw LaTeX, no unicode sub/superscripts.

Open question: confirm the SPEC imports `manim_voiceover.services.gtts` for `GTTSService`; set `tts_import` in `configs/pipeline.yaml`.
Verify every uncertain API with the `manim-docs-lookup` skill.
