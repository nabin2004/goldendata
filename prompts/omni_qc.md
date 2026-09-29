You are given frames from a rendered Manim scene plus a per-frame list of mobject bounding boxes and the beat timeline.
Report JSON only:
{"overlaps":[{"frame":int,"a":str,"b":str}],"clipped":[{"frame":int,"mobject":str}],
 "clutter":bool,"pedagogy_ok":bool,"av_sync_notes":str,"verdict":"pass|fail","suggested_fix":str}
Flag text-over-text overlap, anything crossing the frame edge/margin, and narration that does not match what is on screen.
