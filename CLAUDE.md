# Background remover

Kom sends character sprites (and ID card exports) here to have backgrounds removed. Use the `sprite-background-removal` skill and follow it as written: one `cutout.py` run, one look at the sheet, send the files. Don't read or rewrite the scripts for a normal batch.

- The skill's source of truth is `sprite-background-removal/` in this repo (`SKILL.md` + `scripts/`).
- After changing it, run `python3 tests/check_skill.py`, then package it for Kom with skill-creator's `package_skill.py` and send the `.skill` file so they can click "Save skill".
- The app allows only 5 images per message. If Kom says "more coming", wait for the rest and "go", then do one run over all of them (earlier uploads stay available).
- Hair the generator drew in the bg colour (e.g. Ilse Varga on mint): Kom counts the enclosed bg-coloured areas inside the hair as hair, including the strips along the outer sides of a bob. Background seen between the hair tips and the neck, collar or coat stays clear even when enclosed: filling it gives grey chunks between hair and body (Ilse: pockets beside the neck below the jaw in Neutral, Wary, Angry, Happy; a big wedge in Tired). Tell them apart by the source: a gap is flat, exact bg colour bounded by strand tips and the body; inner hair is a shaded off-bg tone or has strand lines. `tools/fill_hair.py` fills on a cutout; pass `--gap-seeds "x,y;x,y"` (a point in each gap) to keep gaps clear, then check every sprite's neck area over a dark backdrop, not just the worst one.
- Images Kom sends already transparent (cut by another tool) can carry pale halo remnants around the hair. Composite them onto flat green (40,250,90) and run `cutout.py` as usual; its edge pass darkens the remnants to the hair colour.
