# Linter rules
| Rule | Method | Auto-fix |
|---|---|---|
| BOOKMARK_SET_EQUALITY | set(narration bookmarks) == set(wait_until_bookmark args) | no (LLM retry) |
| BOOKMARK_AST_ORDER | `wait_until_bookmark` inside `with self.voiceover` | no |
| KWARG_SIGNATURE_CHECK | `inspect.signature` + MRO + banned list | strip banned kwarg |
| RAW_LATEX_PREFIX | MathTex/Tex string args need `r` prefix | prepend `r` |
| UNICODE_MATH_BAN | unicode sub/superscripts | map to `_x` / `^x` |
| DEPRECATED_API_BAN | `ShowCreation`, `manimlib`, banned methods | rewrite via map |
| FRAME_BOUNDS_CHECK | runtime bbox after `construct()` | wrap in `fit_in_frame` |
| CAMERA_RESTORE_PAIR | `save_state` ↔ `Restore(self.camera.frame)` | no |
| STRUCTURE | two-block, Plan keys/order, section comments, `set_speech_service` first | no |
