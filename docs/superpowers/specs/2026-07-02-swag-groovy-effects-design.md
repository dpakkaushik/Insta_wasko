# Swag Category Groovy Visual Effects — Design

## Problem

Reels in the `swag` category currently go through the same plain pipeline as
every other category: ping-pong looped background, static text card overlay,
audio fade. There's no visual identity that matches "swag" content paired
with groovy music — the output looks identical to `annoyed` reels.

## Scope

Swag-only. Effects are gated by category and do not touch `annoyed` or the
not-yet-active `savage` category. No general per-category effects config is
being introduced now — if more categories want custom treatments later,
that's a separate follow-up.

## Approach

Single-pass extended filter graph. All four effects are folded into the
existing `filter_complex` string built in `compose_reel_with_video_bg()`
in `video_composer.py`, and the whole reel is still encoded once. This
matches the codebase's existing "pure ffmpeg, no MoviePy" approach and
avoids the quality loss and slowdown of re-encoding through multiple
ffmpeg passes (the rejected multi-pass alternative).

## Components

Each effect is a small function that takes the in-progress filter-graph
fragment and returns it extended — so they compose cleanly into the single
filter chain already built in `compose_reel_with_video_bg`.

- `apply_color_pop(fc: str) -> str`
  Appends `eq=saturation=1.3:contrast=1.08:brightness=0.02` to the
  background chain, before the 9:16 crop. Tasteful boost, not blown out.

- `apply_pulsing_zoom(fc: str, duration: float) -> str`
  Appends a `zoompan` stage on the ping-ponged background with a
  sine-based zoom expression, cycling every ~3-4s, giving a rhythmic
  "breathing" feel without real beat-detection.

- `apply_grain(fc: str) -> str`
  Appends `noise=alls=8:allf=t+u` after the card overlay, so grain reads
  as a unified texture across the whole frame (background + card), not
  just the background.

- `apply_light_leak(card_path: str, output_path: str) -> str`
  Generates a warm gradient/glow PNG via PIL (reusing the PIL setup
  already used in `image_composer.py`), saved next to the card as
  `_lightleak_<stem>.png`. Returns the `overlay` + `blend=screen` filter
  stage with time-based `x`/`y` expressions so the glow drifts across the
  frame over the reel duration rather than sitting static.

## Data Flow / Gating

`compose_reel_with_video_bg()` gains an optional `category: str | None`
parameter. Inside `video_composer.py`, the four `apply_*` functions are
only spliced into the filter graph `if category == "swag"`. `main.py`
passes the resolved category through at the existing call site
(`main.py:203`). All other categories flow through unchanged.

## Testing

No automated test suite exists for this pipeline (it's a manual/visual
media pipeline, not logic-heavy code). Verification is manual:

```
py main.py --text "swag: ..." --dry --once
```

Then visually inspect the output MP4 for:
- Saturation reads punchy, not blown out
- Zoom pulse feels rhythmic, not seasick
- Grain is a subtle texture, not visible static
- Light leak drifts warmly without washing out the text card

## Out of Scope

- Real audio beat-detection to sync zoom/effects to the music track
  (the sine-based zoom is a fixed-cycle approximation, not beat-locked)
- Per-category effects configuration system
- Sourcing/licensing a real stock light-leak video asset
