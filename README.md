# Background remover

A Claude skill that cuts flat-colour backgrounds out of character sprite sets, names the files `Full Name, Expression.png` in emotion order, and makes the rounded corners of exported ID cards transparent.

- `sprite-background-removal/SKILL.md` is the skill. The two scripts (`cutout.py`, `card_corners.py`) live inside it, and Claude writes them out and runs them. After changing it here, upload it again to replace the copy in your Claude skills.
- `tests/check_skill.py` takes the scripts out of `SKILL.md` and runs them on synthetic sprites and ID cards whose correct result is known (vivid, pale, gradient, magenta and white backgrounds; hair strands, a sigh puff, a sweat drop, clothes touching the frame; plain and bordered cards). Run it after any change to the skill:

  ```
  pip install -r requirements.txt
  python3 tests/check_skill.py            # --keep DIR to look at the outputs
  ```
