# Background remover

Kom sends character sprites (and ID card exports) here to have backgrounds removed. Use the `sprite-background-removal` skill and follow it as written: one `cutout.py` run, one look at the sheet, send the files. Don't read or rewrite the scripts for a normal batch.

- The skill's source of truth is `sprite-background-removal/` in this repo (`SKILL.md` + `scripts/`).
- After changing it, run `python3 tests/check_skill.py`, then package it for Kom with skill-creator's `package_skill.py` and send the `.skill` file so they can click "Save skill".
- The app allows only 5 images per message. If Kom says "more coming", wait for the rest and "go", then do one run over all of them (earlier uploads stay available).
- Hair the generator drew in the bg colour (e.g. Ilse Varga on mint): Kom counts every enclosed bg-coloured area inside the hair, down to the hair tips and including the back hair behind the neck, as hair. Background seen below the tips, between the hair and the body or coat, stays clear even when enclosed (Ilse's Tired, head tilted: filling it gave a big grey wedge). `tools/fill_hair.py` fills on a cutout; pass `--gap-seeds "x,y"` (a point in each such gap) to keep those clear, then check the neck area over a dark backdrop.
