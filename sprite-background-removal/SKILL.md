---
name: "sprite-background-removal"
description: "Cut flat-colour backgrounds out of character sprite sets and deliver them named 'FullName, Expression' in emotion order; also makes ID card export corners transparent."
---

# Sprite background removal

Use this whenever Kom sends a batch of character sprite renders (Civitai / Illustrious, flat green or other single-colour background) and asks for the background removed, or sends an exported ID card PNG whose rounded corners came out white.

The scripts are in `scripts/` in this skill's folder and are tested. Run them as they are; don't read, rewrite or tune them. They need numpy, Pillow and scipy (`pip install scipy` if the import fails). If `scripts/` is missing, the skill was uploaded without its folder: tell Kom to re-upload the skill zip.

## Sprites

1. **Match each image to an expression** by looking at it (they often arrive out of order). Standard order: Neutral, Happy, Playful, Tired, Sad, Wary, Angry, Shocked, Embarrassed, Thinking.
2. **Run once**, mapping every upload to its expression (uploads are only read):
   ```
   python3 <skill folder>/scripts/cutout.py "Full Name" out 1.webp=Neutral 2.webp=Happy ...
   ```
   It writes `out/Full Name, Expression.png` plus `sheet.png`, and prints one line per image. Add `--keep-tint` only if the character has eyes, clothes or hair in the background's hue.
3. **Look at `sheet.png` once.** Zoom (crop + NEAREST upscale over a dark backdrop) only where a line says `see-through ... at x..-.. y..`: a sigh puff or similar effect there is correct; eyes or clothes there mean the background hue clashes (see below). Don't post-fix the art (pupils, pendants, drawing details): Kom asked for background removal and naming only.
4. **Send** the files from `out/` back as downloads, in the standard order, with whatever file-sharing tool this chat has. One or two lines of summary.

Add to the summary only when it applies:
- `dull bg` (a pale or muted background): it still works; suggest `(vivid green background:1.5)` for the next character.
- See-through eyes or clothes: the character contains the background's hue. Suggest a contrasting key, e.g. `(vivid magenta background:1.5)` for green eyes (not for pink or purple hair).
- `white/grey bg`: white parts may be lost; suggest a vivid green background.

## ID card exports: transparent corners

The Rebis Academy ID card (Design canvas, 2000 CSS px wide, 44 px corner radius) exports as a rectangle, white outside the rounded corners. Run:
```
python3 <skill folder>/scripts/card_corners.py "export.png" "Full Name, ID Card.png"
```
It reads the export scale from the width (a 4000 px export means radius 88 px; `--radius-css` and `--card-width-css` override). Check one corner over a coloured backdrop, then send the file named `Full Name, ID Card.png`.
