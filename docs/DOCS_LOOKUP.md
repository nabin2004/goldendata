# Querying library docs

## 1. Build the local index (once per pinned version)
```bash
python scripts/docs/build_docs_index.py           # Manim CE + manim-voiceover (+ numpy/scipy/sympy)
python scripts/docs/build_docs_index.py --only manim
```
Downloads each project's Sphinx `objects.inv` (a compressed list of every documented object and its URL) into `docs_cache/`.
Sources: `https://docs.manim.community/en/stable/objects.inv`, `https://voiceover.manim.community/en/latest/objects.inv`,
`https://numpy.org/doc/stable/objects.inv`, `https://docs.scipy.org/doc/scipy/objects.inv`, `https://docs.sympy.org/latest/objects.inv`.
If a voiceover inventory is missing, the script reports it; fall back to introspection or the web.

## 2. Search
```bash
python scripts/docs/query_docs.py "ValueTracker"                       # all projects
python scripts/docs/query_docs.py "wait_until_bookmark" -p manim_voiceover
python scripts/docs/query_docs.py "Axes.plot" -p manim --fetch         # print the doc page text
```

## 3. Exact signature from the installed package (authoritative)
```bash
python scripts/docs/api_lookup.py Circle
python scripts/docs/api_lookup.py Circle --methods
python scripts/docs/api_lookup.py manim_voiceover.VoiceoverScene.voiceover
```

## 4. From an agent
- OpenCode: Context7 MCP is enabled in `opencode.json`. Prompt e.g. "use context7 to check `always_redraw` in manim".
- Or call the two scripts above from bash; the `docs-researcher` agent wraps them.

## 5. Human URLs
Manim reference: https://docs.manim.community/en/stable/reference.html · manim-voiceover: https://voiceover.manim.community/
