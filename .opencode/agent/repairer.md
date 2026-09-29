---
description: Produce minimal-diff repairs and V1->diagnosis->V2 traces
mode: subagent
---
Input: failing sample + lint/runtime/vision diagnosis. Use prompts/repair.md.
Change as little as possible. Re-run lint and render before returning. Save the trace to data/repairs/.
