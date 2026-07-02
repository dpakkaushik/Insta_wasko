# Swag Groovy Visual Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four swag-only ffmpeg visual effects (color pop, pulsing zoom, grain, light leak) to the reel-composition pipeline, all rendered together in one pass so the combination can be visually reviewed and tuned afterward.

**Architecture:** All four effects are implemented as small pure functions in `video_composer.py` that return ffmpeg filter-graph fragments (strings). `compose_reel_with_video_bg()` splices them into its existing single `filter_complex` string only when `category == "swag"`. `main.py` passes the resolved category through at its existing call site.

**Tech Stack:** Python 3, ffmpeg (subprocess, filter_complex), Pillow (PIL) for the light-leak glow asset.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-02-swag-groovy-effects-design.md`
- Effects are swag-only — `annoyed` and `savage` must render byte-for-byte the same filter graph as before this change.
- Single-pass filter graph — no additional ffmpeg encode passes.
- Functions named per effect: `apply_color_pop`, `apply_pulsing_zoom`, `apply_grain`, `apply_light_leak`, `_generate_light_leak_png`.
- No test framework exists in this repo (media pipeline, verified manually) — verification steps are manual runs + visual/log inspection, not pytest.

---

### Task 1: Effect helper functions in `video_composer.py`

**Files:**
- Modify: `video_composer.py:1-18` (imports/constants)

**Interfaces:**
- Produces: `apply_color_pop() -> str`, `apply_pulsing_zoom() -> str`, `apply_grain() -> str`, `apply_light_leak(duration: float) -> str`, `_generate_light_leak_png(path: str, size: int = 1600) -> None` — all used by Task 2's `compose_reel_with_video_bg()`.

- [ ] **Step 1: Add the PIL import**

At the top of `video_composer.py`, change:

```python
import json
import random
import subprocess
from pathlib import Path
```

to:

```python
import json
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageOps
```

- [ ] **Step 2: Add the four effect functions + light-leak asset generator**

Insert this new section right after the `TARGET_W, TARGET_H, REEL_DURATION` constants (after line 18, before the `# ── Audio history ──` comment):

```python
# ── Swag-only visual effects ────────────────────────────────────────────────

def apply_color_pop() -> str:
    """Vibrant swag-style saturation/contrast boost."""
    return "eq=saturation=1.3:contrast=1.08:brightness=0.02"


def apply_pulsing_zoom() -> str:
    """Breathing zoom pulse: background scales +/-4% on a 3.5s sine cycle,
    then crops back to the fixed frame so downstream stages see a constant
    size."""
    return (
        f"scale=w='{TARGET_W}*(1+0.04*sin(2*PI*t/3.5))':"
        f"h='{TARGET_H}*(1+0.04*sin(2*PI*t/3.5))':eval=frame,"
        f"crop={TARGET_W}:{TARGET_H}:'(in_w-{TARGET_W})/2':'(in_h-{TARGET_H})/2'"
    )


def apply_grain() -> str:
    """Light film-grain texture over the whole composited frame."""
    return "noise=alls=8:allf=t+u"


def _generate_light_leak_png(path: str, size: int = 1600) -> None:
    """Warm radial glow, alpha-faded from center to edge, saved as an RGBA
    PNG for the light-leak overlay to drift across the frame."""
    gradient = ImageOps.invert(Image.radial_gradient("L")).resize((size, size))
    alpha    = gradient.point(lambda p: int(p * (120 / 255)))
    glow     = Image.new("RGBA", (size, size), (255, 190, 120, 0))
    glow.putalpha(alpha)
    glow.save(path)


def apply_light_leak(duration: float) -> str:
    """Overlay filter fragment: drifts the light-leak PNG in a slow circular
    path across the frame once per full reel duration."""
    return (
        f"overlay=x='-300+400*sin(2*PI*t/{duration})':"
        f"y='-200+300*cos(2*PI*t/{duration})':format=auto"
    )
```

- [ ] **Step 3: Smoke-test the pure functions**

Run:
```bash
py -c "from video_composer import apply_color_pop, apply_pulsing_zoom, apply_grain, apply_light_leak, _generate_light_leak_png; print(apply_color_pop()); print(apply_pulsing_zoom()); print(apply_grain()); print(apply_light_leak(30.0)); _generate_light_leak_png('_scratch_lightleak_test.png'); import os; print('PNG created:', os.path.exists('_scratch_lightleak_test.png')); os.remove('_scratch_lightleak_test.png')"
```

Expected: four filter-fragment strings print without error, followed by `PNG created: True`, and no traceback.

- [ ] **Step 4: Commit**

```bash
git add video_composer.py
git commit -m "feat: add swag-only ffmpeg effect helper functions"
```

---

### Task 2: Wire effects into the pipeline + thread category through

**Files:**
- Modify: `video_composer.py:121-202` (`compose_reel_with_video_bg`)
- Modify: `main.py:203-205` (call site)

**Interfaces:**
- Consumes: `apply_color_pop() -> str`, `apply_pulsing_zoom() -> str`, `apply_grain() -> str`, `apply_light_leak(duration: float) -> str`, `_generate_light_leak_png(path: str, size: int = 1600) -> None` (Task 1)
- Produces: `compose_reel_with_video_bg(card_path, video_bg_path, output_path, audio_dir, duration=REEL_DURATION, category=None) -> tuple[str, str | None]` — new `category` param, backward-compatible default `None` (no effects).

- [ ] **Step 1: Replace `compose_reel_with_video_bg` in `video_composer.py`**

Replace the entire function body (currently `video_composer.py:121-202`, from `def compose_reel_with_video_bg(` through the final `return output_path, audio_name`) with:

```python
def compose_reel_with_video_bg(
    card_path: str,
    video_bg_path: str,
    output_path: str,
    audio_dir: Path,
    duration: float = REEL_DURATION,
    category: str | None = None,
) -> tuple[str, str | None]:
    """
    Compose the final reel using pure ffmpeg subprocess — no MoviePy.

    Inputs:
      [0] video background, ping-ponged (boomerang) and stream-looped to fill
          `duration` — guaranteed seamless at the loop boundary
      [1] card PNG (RGBA), looped as static image
      [2] optional swag light-leak PNG, looped as static image (swag only)
      [3 or 2] optional music track (random sample)

    Filter graph:
      scale + crop to 9:16 -> [swag: color pop + pulsing zoom] -> overlay card
      -> [swag: grain -> light-leak drift] -> fade-out audio

    `category` gates the swag-only effects (color pop, pulsing zoom, grain,
    light leak) — pass "swag" to enable them. Any other value (including the
    default None) renders the plain pipeline, unchanged from before.
    """
    print(f"  [video] Background: {Path(video_bg_path).name}")

    pingpong_path = str(Path(output_path).with_name(f"_pingpong_{Path(output_path).stem}.mp4"))
    _build_pingpong_unit(video_bg_path, pingpong_path)

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-t", str(duration), "-i", pingpong_path,
        "-loop", "1",          "-t", str(duration), "-i", card_path,
    ]

    apply_swag_fx   = category == "swag"
    light_leak_path = None
    light_leak_idx  = None
    if apply_swag_fx:
        light_leak_path = str(Path(output_path).with_name(f"_lightleak_{Path(output_path).stem}.png"))
        _generate_light_leak_png(light_leak_path)
        cmd += ["-loop", "1", "-t", str(duration), "-i", light_leak_path]
        light_leak_idx = 2

    audio_name = None
    music_idx  = None
    fade_start = duration - 1.5

    result = _pick_audio(audio_dir)
    if result:
        music_path, audio_name = result
        raw_dur   = _audio_duration(music_path)
        use_dur   = min(duration, raw_dur)
        max_start = max(0.0, raw_dur - use_dur)
        start     = random.uniform(0, max_start)
        fade_start = max(0.0, use_dur - 1.5)
        print(f"  [audio] Track: {audio_name}, sample {start:.1f}s-{start + use_dur:.1f}s")
        cmd += ["-ss", str(start), "-t", str(use_dur), "-i", music_path]
        music_idx = 3 if apply_swag_fx else 2

    # Scale bg to fill frame, crop to exact 9:16, overlay RGBA card
    bg_chain = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},setsar=1"
    )
    if apply_swag_fx:
        bg_chain += f",{apply_color_pop()},{apply_pulsing_zoom()}"

    fc = f"[0:v]{bg_chain}[bg];[bg][1:v]overlay=0:0:format=auto[v]"

    final_label = "[v]"
    if apply_swag_fx:
        fc += f";[v]{apply_grain()}[vgrain]"
        fc += f";[vgrain][{light_leak_idx}:v]{apply_light_leak(duration)}[vout]"
        final_label = "[vout]"

    if music_idx is not None:
        fc += f";[{music_idx}:a]afade=t=out:st={fade_start:.2f}:d=1.5[aout]"
        audio_map = ["-map", "[aout]"]
    else:
        audio_map = ["-map", "0:a?"]

    cmd += [
        "-filter_complex", fc,
        "-map", final_label,
        *audio_map,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors="replace")
            raise RuntimeError(
                f"[video] ffmpeg composition failed:\n{stderr[-800:]}"
            )
    finally:
        Path(pingpong_path).unlink(missing_ok=True)
        if light_leak_path:
            Path(light_leak_path).unlink(missing_ok=True)

    print(f"  [video] Saved: {output_path}")
    return output_path, audio_name
```

- [ ] **Step 2: Thread `category` through from `main.py`**

In `main.py`, change (currently `main.py:203-205`):

```python
            reel_path, audio_name = compose_reel_with_video_bg(
                card_path, video_bg, reel_path, cfg["audio_dir"], duration=REEL_DURATION
            )
```

to:

```python
            reel_path, audio_name = compose_reel_with_video_bg(
                card_path, video_bg, reel_path, cfg["audio_dir"],
                duration=REEL_DURATION, category=category,
            )
```

- [ ] **Step 3: Render a swag test reel with effects on**

Run:
```bash
py main.py --text "swag: Meri chuppi ko meri kamzori mat samajhna, bas kabhi-kabhi main jawab dene ke mood mein nahi hoti." --dry --once
```

Expected: pipeline completes with `Pipeline complete` at the end, no `ffmpeg composition failed` error, and a new `output/reel_<timestamp>.mp4` is created. Check the ffmpeg stderr tail (printed on failure) if it errors — most likely failure points are the `eval=frame` scale expression syntax or the light-leak overlay input index.

- [ ] **Step 4: Regression-check a non-swag category is unaffected**

Run:
```bash
py main.py --text "annoyed: test line for regression check" --dry --once
```

Expected: pipeline completes successfully, same as before this change — no color pop / zoom / grain / light-leak stages involved (verify by eye that the output doesn't look processed differently from the pre-change `reel_20260702_110100.mp4`).

- [ ] **Step 5: Manually inspect the swag render**

Open `output/reel_<timestamp>.mp4` from Step 3 and check:
- Saturation reads punchy, not blown out
- Zoom pulse feels rhythmic, not seasick or jittery
- Grain is a subtle texture, not visible static
- Light leak drifts warmly across the frame without washing out the text card

- [ ] **Step 6: Commit**

```bash
git add video_composer.py main.py
git commit -m "feat: apply groovy visual effects to swag category reels"
```
