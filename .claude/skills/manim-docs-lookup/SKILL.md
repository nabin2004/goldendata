---
name: manim-docs-lookup
description: Look up Manim CE, manim-voiceover, NumPy, SciPy or SymPy API facts (signatures, valid kwargs, whether a class or method exists) before writing or keeping any call. Use whenever an API name, kwarg or method is uncertain, or a linter flags KWARG_SIGNATURE_CHECK or DEPRECATED_API_BAN.
---
# Manim / library docs lookup

Never guess an API. Check in this order and stop at the first authoritative answer.

1. Installed version (authoritative): `python scripts/docs/api_lookup.py Circle` (add `--methods` for public methods).
   "NOT FOUND" means the name is hallucinated: remove or replace it.
2. Local docs index: `python scripts/docs/query_docs.py "always_redraw" -p manim --fetch`
   Projects: manim, manim_voiceover, numpy, scipy, sympy. Rebuild with `python scripts/docs/build_docs_index.py`.
3. Context7 MCP (enabled in opencode.json): ask for the library by name.
4. Web: https://docs.manim.community/en/stable/reference.html and https://voiceover.manim.community/

If sources disagree, installed-version introspection wins. Report: exact signature, valid kwargs, 3-line example, source URL.
`AOSSpeechService` is repo-local: read its source in the AOS monorepo, not the web.
