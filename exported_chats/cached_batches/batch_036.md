# ChatUI Batch batch_036

## 1. SYSTEM.md

````text
You are an expert Manim Community Edition v0.19+ engineer creating robust canonical Manim-AOS training data.

INPUT: The user message is JSONL with exactly 10 source items. Each line has this shape:
{"id":"...","instruction":"...","code":"..."}
Process all 10 lines exactly once and in order. The id is tracking metadata: never copy it into the answer. If code is empty, implement the instruction directly. If code is present, repair or transform it while preserving the requested behavior. Do not invent missing requirements or silently drop an item.

OUTPUT: Return exactly 10 canonical samples, in the same order as the input. Each sample must contain exactly one <Plan>...</Plan> block, one ```python block, and one closing block in this order:
<End>
	<WhatWasBuilt>...</WhatWasBuilt>
	<WhatWasDemonstrated>...</WhatWasDemonstrated>
	<AnimationAndNarration>...</AnimationAndNarration>
	<ExpectedChecks>...</ExpectedChecks>
</End>
Separate samples with one line containing exactly:
--- SAMPLE END ---
Output nothing else: no introduction, headings, IDs, JSON, numbering, or text outside the three required blocks. The End fields must be concise, factual, and in the exact order shown. If the context limit is reached, stop only after a complete End block and wait for Continue; then resume at the next uncompleted item without repeating or renumbering anything.

PLAN: Use exactly these eight keys, in this order, one line each: goal, skills, layout, camera, dynamics, math, narration, validate. The narration line contains the full spoken script and inline tags such as <bookmark mark='b1'/>.

PYTHON: Use exactly these imports:
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService
The scene inherits VoiceoverScene, defines MARGIN = 0.5 and defines and uses fit_in_frame(mob, w_frac=0.9, h_frac=0.9). The first statement in construct() is self.set_speech_service(GTTSService(transcription_model="base")). Use frame-relative layout, raw LaTeX strings, and [SETUP], [LAYOUT], [UPDATER], [BEAT n | sync: label] comments. Use documented Manim CE v0.19+ APIs only.

BOOKMARKS: Every narration bookmark must have exactly one matching self.wait_until_bookmark("...") call inside the same with self.voiceover(...) block. Before camera movement call self.camera.frame.save_state() and restore with Restore(self.camera.frame). Use one ValueTracker with always_redraw or DecimalNumber for changing values; never rebuild MathTex every frame. Do not use banned or deprecated kwargs/APIs.

FINAL CHECK: Before answering, verify there are 10 outputs for 10 inputs, source order is preserved, every sample has exactly one Plan block, Python block, and End block, all eight Plan keys are ordered, End tags are complete and ordered, bookmarks have exact parity, fit_in_frame is used, and no prose appears outside the samples.
````

## 2. JSONL input

````jsonl
{"id":"r00350","instruction":"Create an interactive Manim CE animation demonstrating: Riemann Rectangles adapting dynamically with ValueTracker. Use updaters and ValueTracker.","code":"from manim import *\nimport numpy as np\n\nclass DynamicScene122(Scene):\n    def construct(self):\n        ax = Axes(x_range=[0, 4, 1], y_range=[0, 5, 1], x_length=6, y_length=4)\n        curve = ax.plot(lambda x: 0.5 * x**2, color=BLUE)\n        k = ValueTracker(4)\n        rects = always_redraw(lambda: ax.get_riemann_rectangles(\n            curve, x_range=[0, 3], dx=3.0 / max(int(k.get_value()), 1), stroke_color=WHITE, fill_opacity=0.6\n        ))\n        count_text = Integer(4).to_corner(UL)\n        count_text.add_updater(lambda m: m.set_value(int(k.get_value())))\n        \n        self.add(ax, curve, rects, count_text)\n        self.play(k.animate.set_value(30), run_time=4, rate_func=linear)\n        self.wait(1)"}
{"id":"r00351","instruction":"Write a Manim CE visualization using scientific Python libraries (numpy, scipy, sympy) for: Fourier Series Square Wave Approximation with NumPy.","code":"from manim import *\nimport numpy as np\n\nclass SciComputeScene1233(Scene):\n    def construct(self):\n        ax = Axes(x_range=[-PI, PI, PI/2], y_range=[-1.5, 1.5, 0.5], x_length=7, y_length=4)\n        self.add(ax)\n        \n        def fourier_square(x, n_terms):\n            y = np.zeros_like(x)\n            for k in range(1, n_terms + 1):\n                n = 2 * k - 1\n                y += (4.0 / (np.pi * n)) * np.sin(n * x)\n            return y\n        \n        for n in [1, 3, 7, 15]:\n            curve = ax.plot(lambda x: fourier_square(np.array([x]), n)[0], color=interpolate_color(BLUE, YELLOW, n/15))\n            label = MathTex(f\"N = {n}\").to_corner(UR)\n            self.play(Create(curve), Write(label), run_time=1.5)\n            self.wait(0.5)\n            if n != 15:\n                self.play(FadeOut(curve), FadeOut(label), run_time=0.5)"}
{"id":"r00352","instruction":"Write a Manim CE visualization using scientific Python libraries (numpy, scipy, sympy) for: Lorenz Attractor Differential Equation with SciPy solve_ivp.","code":"from manim import *\nimport numpy as np\nfrom scipy.integrate import solve_ivp\n\nclass SciComputeScene486(Scene):\n    def construct(self):\n        from scipy.integrate import solve_ivp\n        \n        def lorenz(t, state, sigma=10.0, rho=28.0, beta=8.0/3.0):\n            x, y, z = state\n            return [sigma * (y - x), x * (rho - z) - y, x * y - beta * z]\n        \n        t_eval = np.linspace(0, 20, 2000)\n        sol = solve_ivp(lorenz, (0, 20), [1.0, 1.0, 1.0], t_eval=t_eval)\n        \n        # Scale coordinates to fit Manim screen (2D projection x vs z)\n        points = [np.array([sol.y[0][i] * 0.15, (sol.y[2][i] - 25) * 0.12, 0]) for i in range(len(t_eval))]\n        path = VMobject(color=TEAL, stroke_width=2)\n        path.set_points_as_corners(points[:10])\n        \n        dot = Dot(points[0], color=YELLOW, radius=0.08)\n        self.add(path, dot)\n        \n        step = ValueTracker(10)\n        def update_path(mob):\n            idx = int(step.get_value())\n            mob.set_points_as_corners(points[:idx])\n        \n        path.add_updater(update_path)\n        dot.add_updater(lambda d: d.move_to(points[min(int(step.get_value()), len(points)-1)]))\n        \n        self.play(step.animate.set_value(len(points)-1), run_time=6, rate_func=linear)\n        self.wait(1)"}
{"id":"r00353","instruction":"Construct a clean Manim CE scene initializing TangentLine with verified keyword arguments. Ensure no deprecated ManimGL arguments (like element_color, max_value, or max_magnitude) are used.","code":"from manim import *\nimport numpy as np\n\nclass ApiValidTangentLine9(Scene):\n    def construct(self):\n        obj = TangentLine(Circle(radius=1.5), alpha=0.25, length=3, color=YELLOW)\n        obj.set_color(BLUE)\n        self.play(Create(obj))\n        self.wait(1)"}
{"id":"r00354","instruction":"Write a Manim CE visualization using scientific Python libraries (numpy, scipy, sympy) for: Lorenz Attractor Differential Equation with SciPy solve_ivp.","code":"from manim import *\nimport numpy as np\nfrom scipy.integrate import solve_ivp\n\nclass SciComputeScene974(Scene):\n    def construct(self):\n        from scipy.integrate import solve_ivp\n        \n        def lorenz(t, state, sigma=10.0, rho=28.0, beta=8.0/3.0):\n            x, y, z = state\n            return [sigma * (y - x), x * (rho - z) - y, x * y - beta * z]\n        \n        t_eval = np.linspace(0, 20, 2000)\n        sol = solve_ivp(lorenz, (0, 20), [1.0, 1.0, 1.0], t_eval=t_eval)\n        \n        # Scale coordinates to fit Manim screen (2D projection x vs z)\n        points = [np.array([sol.y[0][i] * 0.15, (sol.y[2][i] - 25) * 0.12, 0]) for i in range(len(t_eval))]\n        path = VMobject(color=TEAL, stroke_width=2)\n        path.set_points_as_corners(points[:10])\n        \n        dot = Dot(points[0], color=YELLOW, radius=0.08)\n        self.add(path, dot)\n        \n        step = ValueTracker(10)\n        def update_path(mob):\n            idx = int(step.get_value())\n            mob.set_points_as_corners(points[:idx])\n        \n        path.add_updater(update_path)\n        dot.add_updater(lambda d: d.move_to(points[min(int(step.get_value()), len(points)-1)]))\n        \n        self.play(step.animate.set_value(len(points)-1), run_time=6, rate_func=linear)\n        self.wait(1)"}
{"id":"r00355","instruction":"Create a step-by-step educational Manim CE lecture scene explaining: Gradient Descent Optimization on 2D Quadratic Function.","code":"from manim import *\nimport numpy as np\n\nclass PedagogicalScene960(Scene):\n    def construct(self):\n        title = Title(r\"Gradient Descent: $x_{k+1} = x_k - \\gamma \\nabla f(x_k)$\")\n        ax = Axes(x_range=[-3, 3, 1], y_range=[0, 9, 3], x_length=6, y_length=4)\n        parabola = ax.plot(lambda x: x**2, color=BLUE)\n        \n        gamma = 0.4\n        x_val = 2.5\n        dot = Dot(ax.c2p(x_val, x_val**2), color=RED)\n        \n        self.play(Write(title), Create(ax), Create(parabola), FadeIn(dot))\n        for step in range(5):\n            grad = 2 * x_val\n            next_x = x_val - gamma * grad\n            arrow = Arrow(ax.c2p(x_val, x_val**2), ax.c2p(next_x, next_x**2), color=YELLOW, buff=0)\n            self.play(GrowArrow(arrow), dot.animate.move_to(ax.c2p(next_x, next_x**2)), run_time=0.8)\n            self.remove(arrow)\n            x_val = next_x\n        self.wait(1)"}
{"id":"r00356","instruction":"Create a step-by-step educational Manim CE lecture scene explaining: Taylor Series Expansion of exp(x).","code":"from manim import *\nimport numpy as np\n\nclass PedagogicalScene878(Scene):\n    def construct(self):\n        title = Title(r\"Taylor Series of $f(x) = e^x$ around $x=0$\")\n        ax = Axes(x_range=[-3, 3, 1], y_range=[-1, 8, 2], x_length=6, y_length=4)\n        exp_curve = ax.plot(lambda x: np.exp(x), color=WHITE)\n        exp_label = MathTex(r\"e^x\").next_to(ax.c2p(2, np.exp(2)), RIGHT)\n        \n        t1 = ax.plot(lambda x: 1 + x, color=BLUE)\n        t2 = ax.plot(lambda x: 1 + x + 0.5 * x**2, color=GREEN)\n        t3 = ax.plot(lambda x: 1 + x + 0.5 * x**2 + (1/6) * x**3, color=YELLOW)\n        \n        self.play(Write(title), Create(ax), Create(exp_curve), Write(exp_label))\n        self.play(Create(t1), run_time=1.5)\n        self.wait(0.5)\n        self.play(Transform(t1, t2), run_time=1.5)\n        self.wait(0.5)\n        self.play(Transform(t1, t3), run_time=1.5)\n        self.wait(2)"}
{"id":"r00357","instruction":"Write a Manim CE visualization using scientific Python libraries (numpy, scipy, sympy) for: Linear Algebra 2D Matrix Eigenvector Transformation.","code":"from manim import *\nimport numpy as np\n\nclass SciComputeScene1300(Scene):\n    def construct(self):\n        plane = NumberPlane(x_range=[-4, 4, 1], y_range=[-3, 3, 1])\n        A = np.array([[2.0, 1.0], [1.0, 2.0]])\n        eigenvalues, eigenvectors = np.linalg.eig(A)\n        \n        v1 = eigenvectors[:, 0]\n        v2 = eigenvectors[:, 1]\n        \n        vec1 = Arrow(ORIGIN, plane.c2p(v1[0], v1[1]), color=RED, buff=0)\n        vec2 = Arrow(ORIGIN, plane.c2p(v2[0], v2[1]), color=GREEN, buff=0)\n        \n        label_v1 = MathTex(r\"\\mathbf{v}_1\", color=RED).next_to(vec1.get_end(), UP)\n        label_v2 = MathTex(r\"\\mathbf{v}_2\", color=GREEN).next_to(vec2.get_end(), RIGHT)\n        \n        self.add(plane, vec1, vec2, label_v1, label_v2)\n        self.play(\n            plane.animate.apply_matrix(A),\n            vec1.animate.put_start_and_end_on(ORIGIN, plane.c2p(*(A @ v1))),\n            vec2.animate.put_start_and_end_on(ORIGIN, plane.c2p(*(A @ v2))),\n            run_time=3\n        )\n        self.wait(1)"}
{"id":"r00358","instruction":"The following Manim CE script crashed with this traceback:\n\n```text\nValueError: latex error converting to dvi. Unicode character ₁ (U+2081) not supported.\n```\n\nFix the bug and provide the corrected, fully compilable Manim CE code:\n\n```python\nfrom manim import *\nimport numpy as np\n\nclass ApiValidTable19(Scene):\n    def construct(self):\n        t = MathTex('w₁ + x²')\n        obj = Table([['1', '2'], ['3', '4']], col_labels=[Text('X'), Text('Y')], row_labels=[Text('R1'), Text('R2')])\n        obj.set_color(RED)\n        self.play(Create(obj))\n        self.wait(1)\n```","code":""}
{"id":"r00359","instruction":"Create a step-by-step educational Manim CE lecture scene explaining: Gradient Descent Optimization on 2D Quadratic Function.","code":"from manim import *\nimport numpy as np\n\nclass PedagogicalScene153(Scene):\n    def construct(self):\n        title = Title(r\"Gradient Descent: $x_{k+1} = x_k - \\gamma \\nabla f(x_k)$\")\n        ax = Axes(x_range=[-3, 3, 1], y_range=[0, 9, 3], x_length=6, y_length=4)\n        parabola = ax.plot(lambda x: x**2, color=BLUE)\n        \n        gamma = 0.4\n        x_val = 2.5\n        dot = Dot(ax.c2p(x_val, x_val**2), color=RED)\n        \n        self.play(Write(title), Create(ax), Create(parabola), FadeIn(dot))\n        for step in range(5):\n            grad = 2 * x_val\n            next_x = x_val - gamma * grad\n            arrow = Arrow(ax.c2p(x_val, x_val**2), ax.c2p(next_x, next_x**2), color=YELLOW, buff=0)\n            self.play(GrowArrow(arrow), dot.animate.move_to(ax.c2p(next_x, next_x**2)), run_time=0.8)\n            self.remove(arrow)\n            x_val = next_x\n        self.wait(1)"}
````

## 3. SKILL.md

````markdown
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
````

## 4. MANIM_COMPOSER.md

````markdown
---
name: manim-composer
description: |
  Trigger when: (1) User wants to create an educational/explainer video, (2) User has a vague concept they want visualized, (3) User mentions "3b1b style" or "explain like 3Blue1Brown", (4) User wants to plan a Manim video or animation sequence, (5) User asks to "compose" or "plan" a math/science visualization.

  Transforms vague video ideas into detailed scene-by-scene plans (scenes.md). Conducts research, asks clarifying questions about audience/scope/focus, and outputs comprehensive scene specifications ready for implementation with ManimCE or ManimGL.

  Use this BEFORE writing any Manim code. This skill plans the video; use manimce-best-practices or manimgl-best-practices for implementation.
---

## Workflow

### Phase 1: Understand the Concept

1. **Research the topic** deeply before asking questions
   - Use web search to understand the core concepts
   - Identify the key insights that make this topic interesting
   - Find the "aha moment" - what makes this click for learners
   - Note common misconceptions to address

2. **Identify the narrative hook**
   - What question does this video answer?
   - Why should the viewer care?
   - What's the surprising or counterintuitive element?

### Phase 2: Clarify with User

Ask targeted questions (not all at once - adapt based on responses):

**Audience & Scope**
- What math/science background should I assume? (e.g., "knows calculus" or "high school algebra")
- Target video length? (short: 5-10min, medium: 15-20min, long: 30min+)
- Should this be self-contained or part of a series?

**Focus & Depth**
- Any specific aspects to emphasize or skip?
- Proof-heavy or intuition-focused?
- Real-world applications to include?

**Style Preferences**
- Color scheme preferences?
- Narration style? (casual, formal, playful)
- Any specific visual metaphors you have in mind?

### Phase 3: Create scenes.md

Output a comprehensive `scenes.md` file with this structure:

```markdown
# [Video Title]

## Overview
- **Topic**: [Core concept]
- **Hook**: [Opening question/mystery]
- **Target Audience**: [Prerequisites]
- **Estimated Length**: [X minutes]
- **Key Insight**: [The "aha moment"]

## Narrative Arc
[2-3 sentences describing the journey from confusion to understanding]

---

## Scene 1: [Scene Name]
**Duration**: ~X seconds
**Purpose**: [What this scene accomplishes]

### Visual Elements
- [List of mobjects needed]
- [Animations to use]
- [Camera movements]

### Content
[Detailed description of what happens, what's shown, what's explained]

### Narration Notes
[Key points to convey, tone, pacing notes]

### Technical Notes
- [Specific Manim classes/methods to use]
- [Any tricky implementations to note]

---

## Scene 2: [Scene Name]
...

---

## Transitions & Flow
[Notes on how scenes connect, recurring visual motifs]

## Color Palette
- Primary: [color] - used for [purpose]
- Secondary: [color] - used for [purpose]
- Accent: [color] - used for [purpose]
- Background: [color]

## Mathematical Content
[List of equations, formulas, or mathematical objects that need to be rendered]

## Implementation Order
[Suggested order for implementing scenes, noting dependencies]
```

## 3b1b Style Principles

Apply these principles when composing scenes:

### Visual Storytelling
- **Show, don't just tell** - Every concept needs a visual representation
- **Progressive revelation** - Build complexity gradually, don't show everything at once
- **Visual continuity** - Transform objects rather than replacing them when possible

### Pacing & Rhythm
- **Pause for insight** - Give viewers time to absorb key moments
- **Vary the pace** - Mix quick sequences with slower explanations
- **End scenes with resolution** - Each scene should feel complete

### Mathematical Beauty
- **Emphasize elegance** - Highlight when math is surprisingly simple or beautiful
- **Connect representations** - Show the same concept multiple ways (algebraic, geometric, intuitive)
- **Embrace abstraction gradually** - Start concrete, then generalize

### Engagement Techniques
- **Pose questions** - Make viewers curious before revealing answers
- **Acknowledge difficulty** - "This might seem confusing at first..."
- **Celebrate insight** - Make the "aha moment" feel earned

## References

- [references/narrative-patterns.md](references/narrative-patterns.md) - Common 3b1b narrative structures
- [references/visual-techniques.md](references/visual-techniques.md) - Effective visualization patterns
- [references/scene-examples.md](references/scene-examples.md) - Example scenes.md excerpts

## Templates

- [templates/scenes-template.md](templates/scenes-template.md) - Blank scenes.md template
````
