# Fonts

## telugu_bold.ttf — Noto Sans Telugu Bold

Used for on-screen Telugu subtitles (`utils/video.render_text_image`).

- Copyright 2010, 2012–2020 Google Inc.; 2015–2020 Google LLC.
- Licensed under the **SIL Open Font License, Version 1.1** (OFL-1.1).
- Upstream: https://github.com/notofonts/noto-fonts

Shipped in the repo rather than loaded from the host because Telugu rendering
must not depend on which fonts a machine happens to have installed — a missing
font renders every subtitle as empty boxes, and the failure is silent.

Telugu is a complex script: correct output needs both this font **and** glyph
shaping. Pillow provides shaping through libraqm; `PIL.features.check("raqm")`
must be true, or conjuncts (ల్ల, క్ష, ద్భ) will render as disconnected pieces.

## bold_font.ttf

The original Latin display font, kept for Latin-only text. It has no Telugu
coverage at all.
