"""
Compose a 30-second MP4 Reel using pure ffmpeg subprocess:
  - Video background ping-ponged (boomerang: forward, reversed, forward...) to
    fill 30 s, center-cropped to 9:16 — always seamless at the loop boundary
    since a reversed clip returns exactly to its starting frame
  - Semi-transparent text card overlaid (RGBA alpha-blended)
  - Random 30-second sample from audio/ mixed in with fade-out
  - No-repeat: same track won't play again for the next 3 runs
"""

import json
import random
import subprocess
from pathlib import Path

AUDIO_NO_REPEAT = 3
TARGET_W, TARGET_H = 1080, 1920
REEL_DURATION = 30.0


# ── Audio history ──────────────────────────────────────────────────────────────

def _history_file(audio_dir: Path) -> Path:
    return Path(f"audio_history_{audio_dir.name}.json")


def _load_audio_history(audio_dir: Path) -> list[str]:
    history_file = _history_file(audio_dir)
    if history_file.exists():
        return json.loads(history_file.read_text())
    return []


def _save_audio_history(audio_dir: Path, track_name: str) -> None:
    history = _load_audio_history(audio_dir)
    history.insert(0, track_name)
    _history_file(audio_dir).write_text(json.dumps(history[:AUDIO_NO_REPEAT]))


def _pick_audio(audio_dir: Path) -> tuple[str, str] | None:
    if not audio_dir.exists():
        return None
    tracks = (
        list(audio_dir.glob("*.mp3"))
        + list(audio_dir.glob("*.m4a"))
        + list(audio_dir.glob("*.wav"))
    )
    if not tracks:
        return None
    history  = _load_audio_history(audio_dir)
    excluded = set(history[:AUDIO_NO_REPEAT])
    pool     = [t for t in tracks if t.name not in excluded]
    if not pool:
        pool = tracks
    chosen = random.choice(pool)
    _save_audio_history(audio_dir, chosen.name)
    return str(chosen), chosen.stem


def _audio_duration(path: str) -> float:
    """Return duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1",
         path],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except Exception:
        return REEL_DURATION


def _has_audio_stream(path: str) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def _build_pingpong_unit(video_bg_path: str, tmp_path: str) -> str:
    """
    Build a forward+reversed 'boomerang' clip (video and audio reversed
    together, in sync) so it can be stream-looped with a guaranteed-seamless
    boundary, regardless of whether the source clip loops cleanly on its own.
    """
    has_audio = _has_audio_stream(video_bg_path)
    if has_audio:
        fc = (
            "[0:v]split[v1][v2];[v2]reverse[v2r];"
            "[0:a]asplit[a1][a2];[a2]areverse[a2r];"
            "[v1][a1][v2r][a2r]concat=n=2:v=1:a=1[v][a]"
        )
        maps = ["-map", "[v]", "-map", "[a]"]
        audio_codec = ["-c:a", "aac"]
    else:
        fc = "[0:v]split[v1][v2];[v2]reverse[v2r];[v1][v2r]concat=n=2:v=1:a=0[v]"
        maps = ["-map", "[v]"]
        audio_codec = []

    cmd = [
        "ffmpeg", "-y", "-i", video_bg_path,
        "-filter_complex", fc,
        *maps,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        *audio_codec,
        tmp_path,
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode(errors="replace")
        raise RuntimeError(f"[video] ping-pong build failed:\n{stderr[-800:]}")
    return tmp_path


# ── Main composition ───────────────────────────────────────────────────────────

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
      [2] optional music track (random sample)

    Filter graph:
      scale + crop to 9:16 -> overlay card (alpha-blended) -> fade-out audio
    """
    print(f"  [video] Background: {Path(video_bg_path).name}")

    preserve_video = category in ("main", "main_character")
    pingpong_path = None

    if preserve_video:
        print("  [video] main: using uploaded video without ping-pong/scale/crop")
        bg_input_path = video_bg_path
    else:
        pingpong_path = str(Path(output_path).with_name(f"_pingpong_{Path(output_path).stem}.mp4"))
        _build_pingpong_unit(video_bg_path, pingpong_path)
        bg_input_path = pingpong_path

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-t", str(duration), "-i", bg_input_path,
        "-loop", "1",          "-t", str(duration), "-i", card_path,
    ]

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
        music_idx = 2

    if preserve_video:
        fc = "[0:v]setsar=1[bg];[bg][1:v]overlay=0:0:format=auto[v]"
    else:
        # Scale bg to fill frame, crop to exact 9:16, overlay RGBA card
        fc = (
            f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},setsar=1[bg];"
            f"[bg][1:v]overlay=0:0:format=auto[v]"
        )
    if music_idx is not None:
        fc += f";[{music_idx}:a]afade=t=out:st={fade_start:.2f}:d=1.5[aout]"
        audio_map = ["-map", "[aout]"]
    else:
        audio_map = ["-map", "0:a?"]

    cmd += [
        "-filter_complex", fc,
        "-map", "[v]",
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
        if pingpong_path:
            Path(pingpong_path).unlink(missing_ok=True)

    print(f"  [video] Saved: {output_path}")
    return output_path, audio_name


# ── Gradient fallback (dead code -- pipeline fails hard if no video) ───────────

def compose_reel(
    image_paths: list[str],
    output_path: str,
    audio_dir: Path,
    duration: float | None = None,
) -> tuple[str, None]:
    raise RuntimeError(
        "[video] No video background found. "
        "Add an MP4 to the category's video/ folder before posting."
    )
