# Background remover

A Claude skill that cuts flat-colour backgrounds out of character sprite sets, names the files `Full Name, Expression.png` in emotion order, and makes the rounded corners of exported ID cards transparent.

- `sprite-background-removal/` is the skill: `SKILL.md` (short instructions) and `scripts/` (`cutout.py`, `card_corners.py`). Claude runs the scripts as they are instead of writing them out each time, which keeps each run quick and cheap.
- To install or update it in Claude, zip the folder (`zip -r sprite-background-removal.zip sprite-background-removal`) and upload the zip as a skill, replacing the old one. Uploading `SKILL.md` alone won't work; the scripts must come with it.
- `tests/check_skill.py` runs the scripts on synthetic sprites and ID cards whose correct result is known (vivid, pale, gradient, magenta and white backgrounds, some sent through lossy WebP like chat uploads; hair strands, a sigh puff, a sweat drop, clothes and a dark fold running off the frame; plain and bordered cards). It checks the edges as they'd look over a dark and a light scene. Run it after any change to the scripts:

  ```
  pip install -r requirements.txt
  python3 tests/check_skill.py            # --keep DIR to look at the outputs
  ```
