You are an expert Manim Community Edition (manim v0.19+) engineer. Transform the legacy script into a canonical Manim-AOS sample.

# STRICT REQUIREMENTS - MUST FOLLOW EXACTLY

1. Class MUST inherit from VoiceoverScene:
   class MyScene(VoiceoverScene):

2. First statement in construct() MUST be:
   self.set_speech_service(GTTSService(transcription_model="base"))  # Google TTS - zero setup, works instantly
   # IMPORTANT: transcription_model="base" is REQUIRED for bookmark timing to work with wait_until_bookmark()

3. MUST define and use fit_in_frame() method on mobjects:
   def fit_in_frame(self, mob: Mobject, w_frac: float = 0.9, h_frac: float = 0.9) -> Mobject:
       max_w = config.frame_width * w_frac
       max_h = config.frame_height * h_frac
       if mob.width > max_w: mob.width = max_w
       if mob.height > max_h: mob.height = max_h
       return mob

4. Every <bookmark mark='x'/> in narration MUST have matching self.wait_until_bookmark("x")

5. If camera.frame moves, MUST use MovingCameraScene AND save_state() + Restore()

6. Use Create() for animations (NOT ShowCreation from ManimGL)
   Use MathTex() for LaTeX (NOT Tex() with R"" prefix)

7. Use MARGIN = 0.5 and stay within frame bounds

# Use ManimCE best practices from manimce-best-practices skill
- From manim import * (NOT from manimlib import *)
- Use Create() for animations (NOT ShowCreation from ManimGL)
- Use MathTex() for LaTeX
- Always use frame-relative positioning (to_edge, to_corner, next_to, align_to)

Follow docs/SPEC.md exactly. Output ONLY one <Plan>...</Plan> block and one ```python block.

Plan Rules (8 single-line keys, FIXED ORDER):
1. goal: What the scene demonstrates
2. skills: List ManimCE classes used (VoiceoverScene, GTTSService, ValueTracker, always_redraw, etc.)
3. layout: Where elements are positioned
4. camera: Static or MovingCameraScene with key frames
5. dynamics: ValueTracker + always_redraw pattern
6. math: LaTeX formulas used
7. narration: Script with <bookmark mark='x'/> tags
8. validate: How you verify correctness

Code Rules:
- MUST have section comments: # [SETUP] # [LAYOUT] # [UPDATER] # [BEAT n | sync: label]
- Each beat: with self.voiceover(text="...") as t: with wait_until_bookmark inside
- No hard-coded frame sizes; use config.frame_width/height
- Mobjects must stay within frame bounds (|x| <= frame_width/2 - MARGIN, |y| <= frame_height/2 - MARGIN)

Instruction (user-facing prompt for this sample):
{instruction}

Retrieved API notes:
{api_notes}

Legacy script:
{legacy_code}
