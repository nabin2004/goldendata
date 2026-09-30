---
name: manim-aos-master
description: >
  Master skill for the Manim-AOS golden dataset project. Consolidates ALL
  skills: canonical sample, voiceover/AOS, docs lookup, lint/repair, docker
  render, AND the full manimce-best-practices skill (scenes, mobjects,
  animations, LaTeX, updaters, camera, positioning, colors, timing, shapes,
  graphing, text) plus all four agent roles. Single file, fully navigable.
  Load this at the start of any session.
---

# Manim-AOS Master Skill — Complete Reference

> **Single file. Zero hunting.** Every rule, pattern, and checklist in one place.

---

## Navigation Index

| # | Section | When to jump here |
|---|---------|-------------------|
| [1](#1-project-overview) | Project Overview | "What does this repo do?" |
| [2](#2-two-block-contract) | Two-Block Contract | Writing/reviewing any sample |
| [3](#3-plan-block-rules) | Plan Block Rules | Filling the 8-key Plan header |
| [4](#4-python-block-rules) | Python Block Rules | Writing scene code |
| [5](#5-skill--manim-voiceover--tts) | Skill · Voiceover / TTS | Narration, bookmarks, GTTSService |
| [6](#6-skill--manim-docs-lookup) | Skill · Docs Lookup | Uncertain API / kwarg / class |
| [7](#7-skill--canonical-sample-checklist) | Skill · Canonical Checklist | Pre-submission checklist |
| [8](#8-skill--lint--repair) | Skill · Lint and Repair | Sample fails lint/render/QC |
| [9](#9-skill--docker-render) | Skill · Docker Render | Stage-4 headless render |
| [10](#10-manimce--scenes) | ManimCE · Scenes | Scene types, lifecycle, methods |
| [11](#11-manimce--mobjects) | ManimCE · Mobjects | Mobject hierarchy, VMobject |
| [12](#12-manimce--animations) | ManimCE · Animations | .animate, Create, Transform |
| [13](#13-manimce--latex--math) | ManimCE · LaTeX and Math | MathTex, Tex, coloring |
| [14](#14-manimce--updaters--valuetracker) | ManimCE · Updaters | ValueTracker, always_redraw |
| [15](#15-manimce--camera-control) | ManimCE · Camera | MovingCameraScene, zoom, pan, 3D |
| [16](#16-manimce--positioning--layout) | ManimCE · Positioning | next_to, to_edge, align_to |
| [17](#17-manimce--colors) | ManimCE · Colors | Constants, gradients, opacity |
| [18](#18-manimce--timing--rate-functions) | ManimCE · Timing | rate_func, run_time, easing |
| [19](#19-manimce--shapes--geometry) | ManimCE · Shapes | Circle, Square, Polygon, Arc |
| [20](#20-manimce--graphing) | ManimCE · Graphing | Axes, plot, parametric, Riemann |
| [21](#21-manimce--text) | ManimCE · Text | Text, MarkupText, fonts |
| [22](#22-agent--transformer) | Agent · Transformer | Legacy to canonical rewrite |
| [23](#23-agent--repairer) | Agent · Repairer | Minimal-diff repair + DPO trace |
| [24](#24-agent--omni-qc) | Agent · Omni QC | Visual overlap/clipping/AV |
| [25](#25-agent--docs-researcher) | Agent · Docs Researcher | Deep API research |
| [26](#26-linter-rules-quick-reference) | Linter Rules | All lint codes |
| [27](#27-banned-api--kwargs) | Banned API and Kwargs | Forbidden patterns |
| [28](#28-pipeline-stages) | Pipeline Stages | End-to-end data flow |
| [29](#29-qwen-chatui-manual-workflow) | Qwen ChatUI Workflow | 100-at-a-time generation |
| [30](#30-folder-layout) | Folder Layout | Where every file lives |
| [31](#31-commands-cheatsheet) | Commands Cheatsheet | make / python -m quick ref |

---

## 1. Project Overview

Refine `nabin2004/manim-aos-5k400` (5 000+ Manim animations) into a gold SFT + DPO dataset.
Targets: pass@1 approximately 100%, zero hallucinated APIs, Manim CE v0.19+, exact narration/bookmark sync.

- Spec: [`docs/SPEC.md`](../../../docs/SPEC.md)
- Pipeline: [`docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md)
- Manual: [`AGENTS.md`](../../../AGENTS.md)

**NOT for ManimGL/3b1b** — this repo is Manim Community Edition only.

[Back to top](#navigation-index)

---

## 2. Two-Block Contract

One `<Plan>...</Plan>` block immediately followed by one python block. Nothing else.

```
<Plan>
goal: ...
skills: ...
layout: ...
camera: ...
dynamics: ...
math: ...
narration: ... <bookmark mark='b1'/> ... <bookmark mark='b2'/> ...
validate: ...
</Plan>
```

followed by a python block containing:

```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService

MARGIN = 0.5

class MyScene(VoiceoverScene):
    def fit_in_frame(self, mob: Mobject, w_frac=0.9, h_frac=0.9) -> Mobject:
        max_w = config.frame_width * w_frac
        max_h = config.frame_height * h_frac
        if mob.width > max_w: mob.width = max_w
        if mob.height > max_h: mob.height = max_h
        return mob

    def construct(self):
        self.set_speech_service(GTTSService(transcription_model="base"))
        # [SETUP]
        # [LAYOUT]
        # [UPDATER]
        # [BEAT 1 | sync: b1]
        with self.voiceover(text="Narration <bookmark mark='b1'/>") as t:
            self.wait_until_bookmark("b1")
            self.play(...)
```

> **Hard invariant:** `set(bookmark marks in narration)` == `set(wait_until_bookmark args)`
> — linter rule `BOOKMARK_SET_EQUALITY` will reject any mismatch.

[Back to top](#navigation-index)

---

## 3. Plan Block Rules

8 keys, **fixed order**, one single line each:

| Key | What to write |
|-----|---------------|
| `goal` | One sentence: what does this scene teach? |
| `skills` | VoiceoverScene, GTTSService, ValueTracker, always_redraw, ... |
| `layout` | "title top-centre, axes centre, label right of axes" |
| `camera` | `Static` or `MovingCameraScene -- zoom to X at beat 2, restore at beat 4` |
| `dynamics` | `ValueTracker t + always_redraw on curve` or `none` |
| `math` | Raw LaTeX strings e.g. `r"\frac{d}{dx}f(x)"` |
| `narration` | Full script with `<bookmark mark='bN'/>` tags inline |
| `validate` | `render passes -ql, bookmarks b1 b2 fire in order` |

[Back to top](#navigation-index)

---

## 4. Python Block Rules

### Imports (exactly these three)

```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService
```

### Class

```python
class MyScene(VoiceoverScene):                          # no camera move
class MyScene(MovingCameraScene, VoiceoverScene):       # camera moves
```

### First statement of construct()

```python
self.set_speech_service(GTTSService(transcription_model="base"))
```

### Required constant and helper

```python
MARGIN = 0.5

def fit_in_frame(self, mob: Mobject, w_frac=0.9, h_frac=0.9) -> Mobject:
    max_w = config.frame_width * w_frac
    max_h = config.frame_height * h_frac
    if mob.width > max_w: mob.width = max_w
    if mob.height > max_h: mob.height = max_h
    return mob
```

### Section comments (required)

```python
# [SETUP]               # [LAYOUT]            # [UPDATER]
# [BEAT n | sync: label]                       # [CAMERA]
```

### Beat pattern

```python
with self.voiceover(text="...<bookmark mark='b1'/>...") as t:
    self.wait_until_bookmark("b1")
    self.play(...)
```

### Key rules

- ONE `ValueTracker` + `always_redraw`/`DecimalNumber`. NEVER rebuild `MathTex` per frame.
- Camera: `self.camera.frame.save_state()` before move; `Restore(self.camera.frame)` after.
- LaTeX: raw strings `r"..."`. No unicode sub/superscripts.
- Positioning: `next_to / to_edge / to_corner / arrange / align_to`. No hard-coded coords.

[Back to top](#navigation-index)

---

## 5. Skill -- Manim Voiceover / TTS

> Source: [`.claude/skills/manim-voiceover-aos/SKILL.md`](../manim-voiceover-aos/SKILL.md)

**For this repo: always use `GTTSService`** (Google TTS, internet required).

```python
from manim_voiceover.services.gtts import GTTSService
self.set_speech_service(GTTSService(transcription_model="base"))
```

### Host deps

```bash
sudo apt install sox texlive-latex-extra texlive-fonts-recommended texlive-science
kpsewhich standalone.cls && kpsewhich amsmath.sty   # verify LaTeX
```

### Bookmark mechanics

GTTSService splits at each `<bookmark mark='x'/>`, synthesises segments separately,
concatenates audio, fires `wait_until_bookmark("x")` at the exact segment boundary.

```python
with self.voiceover(text="First part <bookmark mark='show'/> now.") as t:
    self.wait_until_bookmark("show")   # fires right after "First part"
    self.play(Create(circle))
```

[Back to top](#navigation-index)

---

## 6. Skill -- Manim Docs Lookup

> Source: [`.claude/skills/manim-docs-lookup/SKILL.md`](../manim-docs-lookup/SKILL.md)

**Never guess an API.** Check in order:

1. `python scripts/docs/api_lookup.py Circle [--methods]` -> "NOT FOUND" = hallucinated
2. `python scripts/docs/query_docs.py "always_redraw" --project manim --fetch`
   Projects: `manim | manim_voiceover | numpy | scipy | sympy`
3. Context7 MCP
4. `https://docs.manim.community/en/stable/reference.html`

Installed-version introspection wins if sources disagree.

[Back to top](#navigation-index)

---

## 7. Skill -- Canonical Sample Checklist

> Source: [`.claude/skills/manim-aos-canonical-sample/SKILL.md`](../manim-aos-canonical-sample/SKILL.md)

- [ ] Exactly `<Plan>...</Plan>` then one python block; no prose outside
- [ ] Plan: 8 keys fixed order -- goal, skills, layout, camera, dynamics, math, narration, validate
- [ ] `set(narration bookmarks)` == `set(wait_until_bookmark args)`; all calls inside `with self.voiceover`
- [ ] `GTTSService(transcription_model="base")` first in `construct()`
- [ ] `fit_in_frame` defined and called; `MARGIN = 0.5`; frame-relative positioning
- [ ] Section comments present
- [ ] One `ValueTracker` + `always_redraw`/`DecimalNumber`; no `MathTex` rebuild per frame
- [ ] Camera: `save_state()` + `Restore()`; `MovingCameraScene` only if camera moves
- [ ] Raw LaTeX; no unicode sub/superscripts
- [ ] All APIs verified with docs-lookup (section 6)
- [ ] `manim -ql` passes; audio generated; Omni QC passes

[Back to top](#navigation-index)

---

## 8. Skill -- Lint and Repair

> Source: [`.claude/skills/dataset-lint-repair/SKILL.md`](../dataset-lint-repair/SKILL.md)

```bash
python -m manim_aos_data.cli lint path/to/sample.py [--no-manim]
```

**Repair order:** deterministic auto-fix first -> LLM for bookmark/layout only -> smallest diff -> re-lint -> re-render -> save trace.

```json
{"id":"s001","signal":"render","v1_code":"...","diagnosis":"...","fix_summary":"...","v2_code":"...","diff_lines":4}
```

Every rejection -> `logs/rejections.jsonl` (append-only, NEVER delete).

[Back to top](#navigation-index)

---

## 9. Skill -- Docker Render

> Source: [`.claude/skills/manim-docker-render/SKILL.md`](../manim-docker-render/SKILL.md)

```bash
make docker-build
RENDER_BACKEND=docker make docker-render
```

- Image: `docker/Dockerfile.render` (manimcommunity/manim + sox + manim-voiceover)
- Pin tag `manim>=0.19,<0.20`
- No `-p` / `-f` flags inside Docker
- Linux: `--user "$(id -u):$(id -g)"`
- SoX / LaTeX errors = fix image, not scene code
- Windows: see [`devnote.md`](../../../devnote.md)

[Back to top](#navigation-index)

---

## 10. ManimCE -- Scenes

> Source: [`manimce-best-practices/rules/scenes.md`](../manimce-best-practices/rules/scenes.md)

```python
class MyScene(Scene):
    def setup(self):                         # before construct()
        self.camera.background_color = BLUE_E

    def construct(self):
        circle = Circle()
        self.play(Create(circle))
        self.wait(1)
```

| Class | Use |
|-------|-----|
| `Scene` | Standard 2D |
| `ThreeDScene` | 3D camera orientation |
| `MovingCameraScene` | 2D zoom/pan |
| `VoiceoverScene` | Narrated (this repo) |

```python
self.add(mob)       self.remove(mob)       self.clear()
self.play(anim, run_time=2)                self.wait(2)
```

```bash
manim -pql file.py Scene1     # specific scene
manim -pql -a file.py         # all scenes
```

[Back to top](#navigation-index)

---

## 11. ManimCE -- Mobjects

> Source: [`manimce-best-practices/rules/mobjects.md`](../manimce-best-practices/rules/mobjects.md)

```
Mobject -> VMobject (Circle, Square, Text, MathTex, Axes, VGroup ...)
        -> ImageMobject | PMobject | Group
```

```python
circle = Circle()      square = Square()       rect = Rectangle(width=4, height=2)
triangle = Triangle()  polygon = Polygon(ORIGIN, RIGHT, UP)
line = Line(LEFT, RIGHT)   arrow = Arrow(LEFT, RIGHT)
```

```python
mob.get_center()  mob.get_top()  mob.get_bottom()  mob.get_left()  mob.get_right()
mob.get_corner(UL)  mob.get_start()  mob.get_end()
circle_copy = circle.copy().shift(RIGHT * 2)
circle = Circle().set_color(RED).shift(LEFT).scale(2)   # method chaining
```

```python
class CustomShape(VMobject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_points_as_corners([LEFT, UP, RIGHT, DOWN, LEFT])
```

[Back to top](#navigation-index)

---

## 12. ManimCE -- Animations

> Source: [`manimce-best-practices/rules/animations.md`](../manimce-best-practices/rules/animations.md)

### .animate (most common)

```python
self.play(square.animate.shift(RIGHT))
self.play(circle.animate.scale(2))
self.play(square.animate.shift(RIGHT).rotate(PI/4).set_color(BLUE))
self.play(Create(circle), run_time=2, rate_func=smooth)
```

### Creation / removal

```python
Create(mob)    FadeIn(mob)    Write(text)    DrawBorderThenFill(mob)    GrowFromCenter(mob)
FadeOut(mob)   Uncreate(mob)  ShrinkToCenter(mob)
```

### Transform

```python
Transform(mob1, mob2)              # morph mob1 into mob2
ReplacementTransform(mob1, mob2)   # replace mob1 with mob2
TransformFromCopy(mob1, mob2)      # keep mob1, make mob2
```

### Grouping

```python
self.play(Create(c), FadeIn(s), Write(t))                              # simultaneous
self.play(LaggedStart(FadeIn(a), FadeIn(b), FadeIn(c), lag_ratio=0.3))# lagged
self.play(Succession(Create(c), FadeIn(s)))                            # sequential
```

[Back to top](#navigation-index)

---

## 13. ManimCE -- LaTeX and Math

> Source: [`manimce-best-practices/rules/latex.md`](../manimce-best-practices/rules/latex.md)

```python
MathTex(r"E = mc^2")                     # auto math mode -- use for pure math
Tex(r"The area is $A = \pi r^2$")        # raw LaTeX -- use for text+math
```

### Common formulas

```python
MathTex(r"\frac{a}{b}")          MathTex(r"\sqrt{2}")
MathTex(r"\int_0^\infty e^{-x} dx")
MathTex(r"\sum_{n=1}^{\infty} \frac{1}{n^2}")
MathTex(r"\alpha + \beta = \gamma")
```

### Coloring

```python
eq = MathTex(r"e^{i\pi} + 1 = 0")
eq.set_color_by_tex("e", RED)
eq.set_color_by_tex(r"\pi", BLUE)

eq = MathTex(r"e^x = x^0 + x^1 + \frac{1}{2}x^2", substrings_to_isolate=["x"])
eq.set_color_by_tex("x", YELLOW)

eq = MathTex("a", "^2", "+", "b", "^2", "=", "c", "^2")
eq[0].set_color(RED)   # a
eq[3].set_color(BLUE)  # b
```

### Symbols

```python
MathTex(r"\alpha \beta \gamma \delta")
MathTex(r"\times \div \pm \leq \geq \neq \approx")
MathTex(r"\rightarrow \Rightarrow \Leftrightarrow")
MathTex(r"\int \iint \oint \partial \nabla")
```

**AOS rule:** always raw strings; never unicode sub/superscripts in LaTeX strings.

[Back to top](#navigation-index)

---

## 14. ManimCE -- Updaters and ValueTracker

> Source: [`manimce-best-practices/rules/updaters.md`](../manimce-best-practices/rules/updaters.md)

### Basic updater

```python
label.add_updater(lambda m: m.next_to(dot, UP))
mob.add_updater(lambda m, dt: m.rotate(dt * PI))   # time-based
```

### ValueTracker

```python
tracker = ValueTracker(0)
number = DecimalNumber(0, num_decimal_places=2)
number.add_updater(lambda m: m.set_value(tracker.get_value()))
self.add(number)
self.play(tracker.animate.set_value(4), run_time=3)
```

### always_redraw

```python
tracker = ValueTracker(1)
line = always_redraw(lambda: Line(LEFT * 2, RIGHT * 2 * tracker.get_value()))
self.add(line)
self.play(tracker.animate.set_value(2), run_time=2)
```

### AOS rule -- never rebuild MathTex per frame

```python
# correct
number = DecimalNumber(0).add_updater(lambda m: m.set_value(t.get_value()))

# WRONG -- very slow
label.add_updater(lambda m: m.become(MathTex(f"x = {t.get_value():.2f}")))
```

### Remove updaters

```python
mob.remove_updater(fn)  mob.clear_updaters()
mob.suspend_updating()  mob.resume_updating()
```

### TracedPath

```python
path = TracedPath(dot.get_center, stroke_width=2, stroke_color=BLUE)
self.add(dot, path)
self.play(dot.animate.shift(RIGHT * 2), run_time=3)
```

[Back to top](#navigation-index)

---

## 15. ManimCE -- Camera Control

> Source: [`manimce-best-practices/rules/camera.md`](../manimce-best-practices/rules/camera.md)

### MovingCameraScene

```python
class ZoomScene(MovingCameraScene):
    def construct(self):
        self.add(Circle(), Square().shift(RIGHT * 3))
        self.play(self.camera.frame.animate.scale(0.5))               # zoom in
        self.play(self.camera.frame.animate.scale(4))                 # zoom out
        self.play(self.camera.frame.animate.move_to(other))           # pan
        self.play(self.camera.frame.animate.scale(0.5).move_to(c))   # both
        self.play(self.camera.frame.animate.set(width=c.width * 1.5))
```

### Save and restore (AOS mandatory)

```python
self.camera.frame.save_state()
self.play(self.camera.frame.animate.scale(0.3).move_to(circle))
self.wait()
self.play(Restore(self.camera.frame))
```

### auto_zoom

```python
self.play(self.camera.auto_zoom(mob, margin=1))
```

### 3D camera

```python
self.set_camera_orientation(phi=75 * DEGREES, theta=-45 * DEGREES)
self.begin_ambient_camera_rotation(rate=0.2)
self.wait(5)
self.stop_ambient_camera_rotation()
self.move_camera(phi=45 * DEGREES, theta=45 * DEGREES, run_time=3)
```

**AOS rule:** `save_state()` before any move; `Restore()` after. Add `MovingCameraScene` only if camera actually moves.

[Back to top](#navigation-index)

---

## 16. ManimCE -- Positioning and Layout

> Source: [`manimce-best-practices/rules/positioning.md`](../manimce-best-practices/rules/positioning.md)

### Coordinate system

```
Origin (0,0,0) = screen centre
UP=[0,1,0]  DOWN=[0,-1,0]  LEFT=[-1,0,0]  RIGHT=[1,0,0]
UL=UP+LEFT  UR=UP+RIGHT  DL=DOWN+LEFT  DR=DOWN+RIGHT
```

### Core methods

```python
mob.move_to(ORIGIN)
mob.move_to(RIGHT * 2 + UP * 1)
mob.shift(RIGHT * 2 + UP * 1)               # relative
mob.next_to(other, RIGHT, buff=0.3)         # relative to another mob
mob.next_to(other, RIGHT, aligned_edge=UP)
mob.align_to(other, LEFT)                   # align edges
mob.to_edge(UP, buff=MARGIN)                # screen edge
mob.to_corner(UL, buff=MARGIN)              # screen corner
mob.center()
```

### Getting positions

```python
mob.get_center()  mob.get_top()  mob.get_bottom()
mob.get_left()    mob.get_right()  mob.get_corner(UL)
```

**AOS rule:** never hard-code pixel coordinates; use `config.frame_width / config.frame_height`.

[Back to top](#navigation-index)

---

## 17. ManimCE -- Colors

> Source: [`manimce-best-practices/rules/colors.md`](../manimce-best-practices/rules/colors.md)

### Constants

```python
RED  GREEN  BLUE  YELLOW  ORANGE  PINK  PURPLE  WHITE  BLACK  GREY
BLUE_A ... BLUE_E   RED_A ... RED_E   GREEN_A ... GREEN_E   (A=lightest, E=darkest)
TEAL  GOLD  MAROON  PURE_RED  PURE_GREEN  PURE_BLUE
```

### Setting color

```python
Circle(color=RED, fill_opacity=0.5, stroke_width=4)
mob.set_color(RED)
mob.set_fill(RED, opacity=0.8)
mob.set_stroke(BLUE, width=4)
mob.set_opacity(0.5)
```

### Hex, gradients, interpolation

```python
Circle(color="#FF5733")
text.set_color_by_gradient(RED, YELLOW, GREEN)
from manim import interpolate_color
mid = interpolate_color(RED, BLUE, 0.5)
```

### ManimColor advanced

```python
from manim import ManimColor
c = ManimColor("#FF0000")
c.lighter()  c.darker()  c.invert()  c.opacity(0.5)  c.interpolate(other, 0.5)
```

[Back to top](#navigation-index)

---

## 18. ManimCE -- Timing and Rate Functions

> Source: [`manimce-best-practices/rules/timing.md`](../manimce-best-practices/rules/timing.md)

```python
self.play(Create(circle), run_time=2, rate_func=smooth)
```

### Common rate functions

```python
smooth          # smooth start/end (default)
linear          # constant speed
rush_into       # start slow, end fast
rush_from       # start fast, end slow
there_and_back  # go and return
lingering       # stay (for AnimationGroup delays)
```

### CSS-like ease

```python
ease_in_sine    ease_out_sine    ease_in_out_sine
ease_in_quad    ease_out_quad    ease_in_out_quad
ease_in_cubic   ease_out_cubic   ease_in_out_cubic
ease_in_expo    ease_out_expo    ease_in_out_expo
ease_out_bounce   ease_out_back
```

### Custom rate function

```python
def my_rate(t):       # t in [0,1] -> progress [0,1]
    return t ** 2
self.play(circle.animate.shift(RIGHT), rate_func=my_rate)
```

[Back to top](#navigation-index)

---

## 19. ManimCE -- Shapes and Geometry

> Source: [`manimce-best-practices/rules/shapes.md`](../manimce-best-practices/rules/shapes.md)

```python
Circle(radius=2, color=BLUE, fill_opacity=0.5, stroke_width=4)
Ellipse(width=4, height=2)
Square(side_length=2)
Rectangle(width=4, height=2)
RoundedRectangle(width=4, height=2, corner_radius=0.5)
Triangle()
Dot(point=RIGHT*2, radius=0.2)
Polygon(ORIGIN, RIGHT*2, UP*3)
RegularPolygon(n=5)   RegularPolygon(n=6)
Star(n=5, outer_radius=2, density=2)
RegularPolygram(5, radius=2)
Annulus(inner_radius=1, outer_radius=2)
Sector(radius=2, angle=PI/2, start_angle=0)
Arc(radius=2, angle=PI/2, start_angle=PI)
ArcBetweenPoints(start=LEFT*2, end=RIGHT*2, angle=PI/2)
Circle.from_three_points(p1, p2, p3)
circle.surround(triangle, buffer_factor=1.5)
```

### Common operations

```python
shape.scale(2)  shape.rotate(PI/4)  shape.stretch(2, dim=0)
shape.set_fill(RED, opacity=0.5)    shape.set_stroke(WHITE, width=4)
```

[Back to top](#navigation-index)

---

## 20. ManimCE -- Graphing

> Source: [`manimce-best-practices/rules/graphing.md`](../manimce-best-practices/rules/graphing.md)

```python
axes = Axes(x_range=[-3, 3], y_range=[-2, 8])
graph = axes.plot(lambda x: x**2, color=BLUE)
graph = axes.plot(lambda x: np.sin(x), x_range=[-PI, PI], color=YELLOW)
label = axes.get_graph_label(graph, label=MathTex("y = x^2"), x_val=2, direction=UR)
```

### Parametric

```python
curve = axes.plot_parametric_curve(
    lambda t: np.array([np.cos(t), np.sin(t), 0]),
    t_range=[0, 2 * PI], color=YELLOW
)
curve = ParametricFunction(lambda t: np.array([np.cos(t), np.sin(t), 0]), t_range=[0, 2*PI])
```

### Area, Riemann, moving dot

```python
area  = axes.get_area(graph, x_range=[0, 2], color=BLUE, opacity=0.5)
rects = axes.get_riemann_rectangles(graph, x_range=[0, 3], dx=0.5)
x_tracker = ValueTracker(-3)
dot = always_redraw(lambda: Dot(axes.i2gp(x_tracker.get_value(), graph), color=YELLOW))
self.play(x_tracker.animate.set_value(3), run_time=4)
```

### 3D surface

```python
class SurfacePlot(ThreeDScene):
    def construct(self):
        axes = ThreeDAxes()
        surface = axes.plot_surface(
            lambda u, v: np.sin(u) * np.cos(v),
            u_range=[-PI, PI], v_range=[-PI, PI],
            colorscale=[BLUE, GREEN, YELLOW]
        )
        self.set_camera_orientation(phi=75*DEGREES, theta=-45*DEGREES)
        self.add(axes, surface)
```

[Back to top](#navigation-index)

---

## 21. ManimCE -- Text

> Source: [`manimce-best-practices/rules/text.md`](../manimce-best-practices/rules/text.md)

```python
Text("Hello World")
Text("Hello World", font_size=48, color=BLUE, font="Arial", weight=BOLD, slant=ITALIC)
```

### Coloring

```python
text = Text("Hello World")
text[0:5].set_color(RED)
text[6:11].set_color(BLUE)
text.set_color_by_gradient(RED, YELLOW, GREEN)
```

### MarkupText -- mixed styles

```python
MarkupText('<b>Bold</b> and <i>Italic</i>')
MarkupText('<span fgcolor="yellow">Yellow</span>')
MarkupText('H<sub>2</sub>O and x<sup>2</sup>')
MarkupText('<u>Underline</u> and <s>Strike</s>')
MarkupText("gradient text", gradient=(BLUE, GREEN))
# Escape: < becomes &lt;  > becomes &gt;  & becomes &amp;
```

### Multi-line

```python
text = Text("Line 1\nLine 2\nLine 3")
para = Paragraph("This is a longer text", "that spans multiple lines", line_spacing=0.5)
```

### Accessing characters

```python
text = Text("ABCDE")
text[0]     # 'A'
text[0:3]   # 'ABC'
for char in text:
    char.set_color(random_color())
```

**Best practices:** `Text` for plain; `MarkupText` for mixed styles; `MathTex` for math (Text does not render LaTeX).

[Back to top](#navigation-index)

---

## 22. Agent -- Transformer

> Source: [`.opencode/agent/transformer.md`](../../../.opencode/agent/transformer.md)

Rewrite legacy triage record -> canonical candidate JSON.

1. Verify APIs with `python scripts/docs/api_lookup.py <Name>`
2. Rewrite with [`prompts/transform.md`](../../../prompts/transform.md)
3. `python -m manim_aos_data.cli lint <file>` -- fix (max 3 rounds)
4. Output canonical JSON or log rejection

[Back to top](#navigation-index)

---

## 23. Agent -- Repairer

> Source: [`.opencode/agent/repairer.md`](../../../.opencode/agent/repairer.md)

Minimal-diff repair + V1->diagnosis->V2 DPO trace.

### Repair prompt (copy-paste into any coding agent)

```
Repair the Manim-AOS script with the SMALLEST possible diff.

Failure signal ({REASON_CODE}):
{PASTE_FULL_ERROR_TRACEBACK_HERE}

V1 code:
{PASTE_FULL_SAMPLE_HERE}

Rules:
- Keep <Plan>...</Plan> unchanged unless bookmark mismatch forces narration edit.
- Do NOT restyle working code.
- Confirm: set(bookmark marks in narration) == set(wait_until_bookmark args).
- Output JSON only: {"diagnosis":"...","fix_summary":"...","v2_code":"..."}
```

Re-run lint **and** render before returning. Save to `data/repairs/<id>.jsonl`.

[Back to top](#navigation-index)

---

## 24. Agent -- Omni QC

> Source: [`.opencode/agent/omni-qc.md`](../../../.opencode/agent/omni-qc.md)

**Input:** `data/rendered/<id>/frames/*.png` + `bbox.json` + `timing.json`

```json
{
  "overlaps":     [{"frame": 3, "a": "MathTex_0", "b": "Text_1"}],
  "clipped":      [{"frame": 5, "mobject": "Arrow_2"}],
  "clutter":      false,
  "pedagogy_ok":  true,
  "av_sync_notes":"b1 fires 0.1s early",
  "verdict":      "pass | fail",
  "suggested_fix":"..."
}
```

Thresholds: `overlap_iou=0.05`, `clip_margin_frac=0.02`, `max_av_drift_s=0.25`

[Back to top](#navigation-index)

---

## 25. Agent -- Docs Researcher

> Source: [`.opencode/agent/docs-researcher.md`](../../../.opencode/agent/docs-researcher.md)

Lookup order: installed introspection -> local docs index -> Context7 MCP -> web.
Return: exact signature + valid kwargs + 3-line example + source URL.
If not found -> `"NOT FOUND (likely hallucinated)"`.

[Back to top](#navigation-index)

---

## 26. Linter Rules Quick Reference

> Full: [`docs/LINTER_RULES.md`](../../../docs/LINTER_RULES.md)

| Rule code | What is checked | Auto-fix? |
|-----------|----------------|-----------|
| `BOOKMARK_SET_EQUALITY` | narration bookmarks == wait_until_bookmark args | No |
| `BOOKMARK_AST_ORDER` | `wait_until_bookmark` inside `with self.voiceover` | No |
| `KWARG_SIGNATURE_CHECK` | kwargs valid per `inspect.signature` + MRO + banned list | Yes |
| `RAW_LATEX_PREFIX` | MathTex/Tex string args need `r` prefix | Yes |
| `UNICODE_MATH_BAN` | unicode sub/superscripts in strings | Yes |
| `DEPRECATED_API_BAN` | ShowCreation, manimlib, banned methods | Yes |
| `FRAME_BOUNDS_CHECK` | runtime bbox within frame | Yes |
| `CAMERA_RESTORE_PAIR` | `save_state` + `Restore(self.camera.frame)` paired | No |
| `STRUCTURE` | two-block, Plan keys/order, section comments, set_speech_service first | No |

[Back to top](#navigation-index)

---

## 27. Banned API and Kwargs

> Sources: [`configs/deprecated_map.yaml`](../../../configs/deprecated_map.yaml) and [`configs/banned_kwargs.yaml`](../../../configs/banned_kwargs.yaml)

| Pattern | Replace with |
|---------|-------------|
| `from manimlib import *` | `from manim import *` |
| `ShowCreation(mob)` | `Create(mob)` |
| `mob.intersect(other)` | `Intersection(mob, other)` |
| `mob.union(other)` | `Union(mob, other)` |

**Global banned kwargs:** `element_color, max_magnitude, font_size_px, center_point`

| Class | Banned kwargs |
|-------|--------------|
| `DecimalNumber` | `max_value` |
| `Text`, `MathTex`, `Dot` | `size` |

**ManimCE vs ManimGL:**

| | ManimCE (this repo) | ManimGL |
|-|---------------------|---------|
| Import | `from manim import *` | `from manimlib import *` |
| CLI | `manim` | `manimgl` |
| Math | `MathTex(r"\pi")` | `Tex(R"\pi")` |

[Back to top](#navigation-index)

---

## 28. Pipeline Stages

```
data/raw/        [1] Ingest + AST triage  ->  rejects: SYNTAX_ERROR, NO_SCENE, MANIMLIB
data/triage/     [2] Transform (LLM/Qwen) ->  rejects: NOT_TWO_BLOCK, PLAN_SCHEMA
data/canonical/  [3] Deterministic linter (section 26)
                 [4] Headless render      ->  rejects: RENDER_FAIL, TTS_FAIL, TIMEOUT
data/rendered/   [5] Omni QC + repair     ->  rejects: OVERLAP, CLIPPED, AV_DRIFT
                 [6] Package
data/packaged/sft.jsonl   [{role:user},{role:assistant}]
data/packaged/dpo.jsonl   {prompt, chosen(V2), rejected(V1)}
```

Repair loop: stages 3-5 failures -> `repair.py` -> max 2 rounds -> `data/repairs/`

[Back to top](#navigation-index)

---

## 29. Qwen ChatUI Manual Workflow

> Full guide: [`docs/QWEN_CHATUI_MANUAL_WORKFLOW.md`](../../../docs/QWEN_CHATUI_MANUAL_WORKFLOW.md)

```
1. Qwen ChatUI -> New Conversation -> Set system prompt (from the workflow doc)
2. Send user prompt with 100 topics (delimiter: "--- SAMPLE END ---")
3. Copy response -> save as data/raw_batches/raw_batch_NNN.txt
4. python scripts/split_batch.py raw_batch_NNN.txt data/canonical_manual/
5. python -m manim_aos_data.render --input data/canonical_manual/ \
       --output data/render_pass/ --fail-dir data/render_fail/
6. For each data/render_fail/ file -> repair prompt (section 23) -> save to data/repairs/
7. Re-render fixed files; move passing ones to data/canonical/
8. Repeat with next 100 topics
```

Keep `scripts/topics.txt` (one topic/line); use `head -100 scripts/topics.txt` per batch.

[Back to top](#navigation-index)

---

## 30. Folder Layout

```
THEGOLDENDATASET/
|-- AGENTS.md
|-- .claude/skills/
|   |-- manim-aos-master/SKILL.md         <- THIS FILE
|   |-- manim-voiceover-aos/SKILL.md      (source)
|   |-- manim-docs-lookup/SKILL.md        (source)
|   |-- manim-aos-canonical-sample/SKILL.md (source)
|   |-- dataset-lint-repair/SKILL.md      (source)
|   |-- manim-docker-render/SKILL.md      (source)
|   `-- manimce-best-practices/
|       |-- SKILL.md   (source)
|       `-- rules/ (scenes, mobjects, animations, latex, updaters, camera,
|                   positioning, colors, timing, shapes, graphing, text, ...)
|-- .opencode/agent/
|   |-- transformer.md  repairer.md  omni-qc.md  docs-researcher.md
|-- configs/
|   |-- pipeline.yaml  banned_kwargs.yaml  deprecated_map.yaml
|-- docs/
|   |-- SPEC.md  ARCHITECTURE.md  LINTER_RULES.md
|   `-- QWEN_CHATUI_MANUAL_WORKFLOW.md
|-- prompts/
|   |-- transform.md  repair.md  omni_qc.md
|-- scripts/
|   `-- split_batch.py
|-- data/
|   |-- raw/  triage/  canonical/  canonical_manual/
|   |-- raw_batches/  render_pass/  render_fail/
|   |-- repairs/  packaged/{sft,dpo}.jsonl
|-- logs/
|   `-- rejections.jsonl   <- append-only, NEVER delete
`-- src/manim_aos_data/linter/
```

[Back to top](#navigation-index)

---

## 31. Commands Cheatsheet

```bash
# Setup
make setup && make docs-index

# API lookup (before any API call)
python scripts/docs/api_lookup.py Circle [--methods]
python scripts/docs/query_docs.py "always_redraw" --project manim --fetch

# Lint
python -m manim_aos_data.cli lint path/to/sample.py [--no-manim]
make lint-sample F=path/to/sample.py

# Pipeline
make triage && make transform && make validate && make render && make omni && make package

# Docker
make docker-build && RENDER_BACKEND=docker make docker-render

# Qwen batch split
python scripts/split_batch.py raw_batch_001.txt data/canonical_manual/

# Single scene (dev / debug)
manim -ql path/to/scene.py MySceneName
manim -pql path/to/scene.py MySceneName       # with preview
manim -pqh path/to/scene.py MySceneName       # high quality
manim --format gif path/to/scene.py Scene
manim checkhealth

# Tests
make test && pytest tests/ -v
```

[Back to top](#navigation-index)

---

*Last updated: 2026-09-30 -- all skills consolidated:
manim-voiceover-aos, manim-docs-lookup, manim-aos-canonical-sample,
dataset-lint-repair, manim-docker-render,
manimce-best-practices (scenes, mobjects, animations, latex, updaters,
camera, positioning, colors, timing, shapes, graphing, text),
agents: transformer, repairer, omni-qc, docs-researcher.*
