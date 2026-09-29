---
name: manim-voiceover-aos
description: Write and edit Manim VoiceoverScene code narrated by the local, offline AOSSpeechService (Pocket TTS) instead of cloud TTS providers (Azure, OpenAI, ElevenLabs). Use this skill any time Manim narration, voiceover, or the AOS audio/speech service comes up — including requests to "add narration to this scene," "make this Manim animation talk," "sync audio to this animation," "use bookmarks for timing," or anything mentioning AOSSpeechService, Pocket TTS, or the apps/audio_service narrator. Also trigger when the user is working in the apps/agents coder workspace and mentions compiling, rendering, or previewing a voiceover scene.
---

# Manim Voiceover + AOS Audio Service

Add narration directly inside Manim scenes using [Manim Voiceover](https://voiceover.manim.community/en/stable/), backed by the local Pocket TTS stack in `apps/audio_service/narrator.py`. This is the **coder agent workspace** integration — it does not apply to the main lecture pipeline's post-render narration (`tools/narrate.py`, `tools/assemble.py`), which stays separate.

## Before writing any scene: check the host dependencies

Manim Voiceover shells out to external tools. If compile logs show `SoX could not be found!`, `/bin/sh: line 1: sox: command not found`, or a LaTeX error, **fix the host install — do not thrash on string-escaping or code changes to work around it.**

**SoX** (required for audio processing):
```bash
# Arch
sudo pacman -S sox
# Debian/Ubuntu
sudo apt install sox
```

**LaTeX** (required for `MathTex`/`Tex`, which use the `standalone` document class):
```bash
# Arch
sudo pacman -S --needed texlive-latexextra texlive-fontsrecommended texlive-mathscience
# Debian/Ubuntu
sudo apt install texlive-latex-extra texlive-fonts-recommended texlive-science
```
Verify with `kpsewhich standalone.cls` and `kpsewhich amsmath.sty`. If either comes back empty, that's the LaTeX install, not the scene code.

## Why AOSSpeechService instead of a cloud TTS service

Manim Voiceover natively supports cloud services (Azure, OpenAI, ElevenLabs, etc.), but AOS scenes should use **`AOSSpeechService`**:
- Runs offline, on CPU, via Pocket TTS — no API keys, no accounts, no cost
- Same `Narrator` engine as the main lecture pipeline

**Note:** For the main dataset pipeline (not the coder agent workspace), use **`GTTSService`** (Google TTS) instead:
- Zero setup: `pip install "manim-voiceover[gtts]"`
- No API keys needed
- Uses Google Translate API (requires internet)

Don't reach for a cloud speech service in this workspace even if the user's request sounds generic ("add a voiceover") — default to `AOSSpeechService`.

## Workspace layout

All coder tools share one folder (default `workspace/coder/`):

```
workspace/coder/
  scene.py              # Manim source
  manifest.json         # structured run history
  logs/compile.log       # manim stdout/stderr
  audio/                 # preview wavs from synthesize_narration
  voiceover_cache/       # manim-voiceover cache (wav + cache.json)
  media/                 # rendered video output
```

## Agent tools

| Tool | Purpose |
| --- | --- |
| `manim_write(code, scene_name, output_dir)` | Write scene source to the workspace |
| `compile_manim_code(code, scene_name, output_dir)` | Render scene via `uv run manim` |
| `synthesize_narration(text, voice, output_dir)` | Preview narration wav without rendering |
| `search_manim_docs` / `search_manim_signatures` | Look up Manim API docs |

All tools return JSON with `ok`, paths, and status — check `manifest.json` for full run history when debugging a failed compile.

## Minimal voiceover scene (use this as the base pattern)

### For AOS coder workspace (offline Pocket TTS):
```python
from manim import *
from manim_voiceover import VoiceoverScene
from tools.aos_speech_service import AOSSpeechService


class IntroScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(
            AOSSpeechService(voice="alba", cache_dir="voiceover_cache")
        )

        circle = Circle()
        with self.voiceover(text="This circle is drawn as I speak.") as tracker:
            self.play(Create(circle), run_time=tracker.duration)
```

### For main pipeline (zero-setup GTTSService):
```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService


class IntroScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService())

        circle = Circle()
        with self.voiceover(text="This circle is drawn as I speak.") as tracker:
            self.play(Create(circle), run_time=tracker.duration)
```

Every voiceover scene needs: (1) `VoiceoverScene` as the base class, (2) `self.set_speech_service(AOSSpeechService(...))` called first in `construct()`, (3) each narrated beat wrapped in `with self.voiceover(text="...") as tracker:`, with the animation's `run_time=tracker.duration` so visuals sync to speech length rather than a guessed duration.

Compile from the agents directory:
```bash
cd apps/agents
uv run python -c "
from tools.compile import compile_manim_code
print(compile_manim_code(open('workspace/coder/scene.py').read(), 'scene'))
"
```

## Available voices

Pass the voice name to both `AOSSpeechService(voice=...)` and `synthesize_narration(text, voice=...)`.

- **English:** `alba` (default), `anna`, `charles`, `mary`, `michael`, and others
- **Other languages:** `giovanni` (IT), `lola` (ES), `juergen` (DE), `rafael` (PT), `estelle` (FR)

## Timing animations to mid-narration moments: bookmarks

Use `wait_until_bookmark` to fire an animation partway through a line of narration, rather than only at the start/end of a voiceover block:

```python
with self.voiceover(
    text="Before we start our <bookmark mark='FOCUS'/>lecture One."
):
    title = Title("Lecture 1: Introduction", font_size=48, color=BLUE)
    self.wait_until_bookmark("FOCUS")
    self.play(Write(title))
```

**How this actually works under the hood (relevant if timing looks off):** Pocket TTS does not emit word-level timestamps, and AOS does not use Whisper for forced alignment. Instead, `AOSSpeechService` splits the narration text at each `<bookmark mark='...'/>` tag, synthesizes each resulting segment as its own Pocket TTS call, concatenates the audio, and returns word boundaries at the segment edges. That means `wait_until_bookmark` lands on the *measured end of the preceding speech segment* — not an estimate. If a bookmark's timing looks wrong, check the segment split (i.e., where the bookmark tag sits in the text), not a timestamp table.

For narration with no bookmarks, synthesis is a single Pocket TTS call — no special handling needed.

## Scope boundary

This integration is for the **coder agent workspace only**. Do not apply this pattern to:
- The main lecture pipeline's narration, which is post-render via `tools/narrate.py` + `tools/assemble.py`
- Docker render (`tools/render.py`), which does not run voiceover scenes in this pass

If a request is ambiguous about which pipeline it belongs to, ask rather than assuming the coder-agent/VoiceoverScene pattern applies.

## Further reading

- [Manim Voiceover docs](https://voiceover.manim.community/en/stable/)
- [Speech services comparison](https://voiceover.manim.community/en/stable/services.html)
- [Quickstart](https://voiceover.manim.community/en/stable/quickstart.html)
