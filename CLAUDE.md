# Background remover

Kom sends character sprites (and ID card exports) here to have backgrounds removed. Use the `sprite-background-removal` skill and follow it as written: one `cutout.py` run, one look at the sheet, send the files. Don't read or rewrite the scripts for a normal batch.

- The skill's source of truth is `sprite-background-removal/` in this repo (`SKILL.md` + `scripts/`).
- After changing it, run `python3 tests/check_skill.py`, then package it for Kom with skill-creator's `package_skill.py` and send the `.skill` file so they can click "Save skill".
- The app allows only 5 images per message. If Kom says "more coming", wait for the rest and "go", then do one run over all of them (earlier uploads stay available).
