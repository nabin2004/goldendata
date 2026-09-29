# Canonical sample spec

## Output contract
Exactly one `<Plan>...</Plan>` block, immediately followed by exactly one ```python block. Nothing before, between or after.

## Plan block
8 keys, fixed order, one single-line entry each: `goal, skills, layout, camera, dynamics, math, narration, validate`.
`narration` carries the script beats with inline `<bookmark mark='x'/>` tags.
Bookmark names in `narration` must equal the names in `wait_until_bookmark("x")` calls (set equality, and ideally same order).

## Code block
- `from manim import *`, `from manim_voiceover import VoiceoverScene`, `from manim_voiceover.services.gtts import GTTSService`
- Class inherits `VoiceoverScene`; add `MovingCameraScene` iff the camera moves.
- First statement of `construct()`: `self.set_speech_service(GTTSService())`
- Defines and uses `fit_in_frame(mob, w_frac=0.9, h_frac=0.9)`; `MARGIN = 0.5`.
- Section comments: `# [SETUP]`, `# [LAYOUT]`, `# [UPDATER]`, `# [BEAT n | sync: label]`, `# [CAMERA]`.
- Each beat is `with self.voiceover(text="...") as tracker:`; all `wait_until_bookmark` calls sit inside it.
- Dynamics: one `ValueTracker` + `always_redraw` / `DecimalNumber` updaters. Never rebuild `MathTex` per frame.
- Camera: `self.camera.frame.save_state()` before moving, `Restore(self.camera.frame)` after.
- LaTeX: raw strings, no unicode sub/superscripts.
- Positioning: `next_to / to_edge / to_corner / arrange / align_to`; sizes from `config.frame_width/height`.

## Reference sample
See `tests/fixtures/good_derivative.py` (the fixture the linter test-suite must accept).

## Notes on the original strategy doc (decisions made here)
- `FRAME_BOUNDS_CHECK` uses the origin-centred frame: `|x| <= frame_width/2`, `|y| <= frame_height/2` (not `0..width`).
- The kwarg check via `inspect.signature` is weak for classes that take `**kwargs` (most Mobjects). The linter therefore also walks the MRO and uses `configs/banned_kwargs.yaml`.
- `Plot` is not a Manim class (`Axes.plot` is a method). `TransformFromCopy` is a real CE class, so it is not auto-rewritten.
- The reference camera snippet used `Restore` without `save_state()`; the linter enforces the pairing.
