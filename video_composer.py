"""
Compose a 30-second MP4 Reel:
  - Video background (10 s) looped 3× to fill 30 s, center-cropped to 9:16
  - Semi-transparent text card overlaid
  - Random 30-second sample from audio/ mixed with the bg's original audio
  - No-repeat: same track won't play again for the next 3 runs
"""

import json
import random
from pathlib import Path

# moviepy 1.x uses PIL.Image.ANTIALIAS which was removed in Pillow 10
import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

OUTPUT_FPS         = 30
AUDIO_DIR          = Path("audio")
AUDIO_HISTORY_FILE = Path("audio_history.json")
AUDIO_NO_REPEAT    = 3


def _load_audio_history() -> list[str]:
    if AUDIO_HISTORY_FILE.exists():
        return json.loads(AUDIO_HISTORY_FILE.read_text())
    return []


def _save_audio_history(track_name: str) -> None:
    history = _load_audio_history()
    history.insert(0, track_name)
    AUDIO_HISTORY_FILE.write_text(json.dumps(history[:AUDIO_NO_REPEAT]))


def _pick_audio() -> str | None:
    if not AUDIO_DIR.exists():
        return None
    tracks = (
        list(AUDIO_DIR.glob("*.mp3"))
        + list(AUDIO_DIR.glob("*.m4a"))
        + list(AUDIO_DIR.glob("*.wav"))
    )
    if not tracks:
        return None
    history  = _load_audio_history()
    excluded = set(history[:AUDIO_NO_REPEAT])
    pool     = [t for t in tracks if t.name not in excluded]
    if not pool:
        pool = tracks  # all recently used — reset
    chosen = random.choice(pool)
    _save_audio_history(chosen.name)
    print(f"  [audio] Track: {chosen.name}")
    return str(chosen), chosen.stem


def compose_reel(
    image_paths: list[str],
    output_path: str,
    duration: float | None = None,
) -> tuple[str, None]:
    """Fallback: still images + random audio sample (no video bg)."""
    try:
        from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
    except ImportError as exc:
        raise RuntimeError(
            "[video] moviepy is not installed. Run: pip install moviepy\n"
            f"Original error: {exc}"
        ) from exc

    slide_dur = duration if duration is not None else 3.0
    print(f"  [video] Composing {len(image_paths)} slide(s) × {slide_dur}s each...")
    try:
        clips  = [ImageClip(p).set_duration(slide_dur) for p in image_paths]
        video  = concatenate_videoclips(clips, method="compose")
        target = video.duration

        audio_name = None
        result = _pick_audio()
        if result:
            audio_path, audio_name = result
            try:
                raw       = AudioFileClip(audio_path)
                max_start = max(0.0, raw.duration - target)
                start     = random.uniform(0, max_start)
                music     = raw.subclip(start, start + target).audio_fadeout(1.5)
                video     = video.set_audio(music)
            except Exception as exc:
                print(f"  [video] WARNING: audio failed ({exc}) — posting silent")

        video.write_videofile(
            output_path,
            fps=OUTPUT_FPS,
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None,
        )
        print(f"  [video] Saved: {output_path}")
        return output_path, audio_name
    except Exception as exc:
        raise RuntimeError(
            f"[video] Reel composition failed: {type(exc).__name__}: {exc}\n"
            "Check that ffmpeg is installed and all slide images exist."
        ) from exc


def compose_reel_with_video_bg(
    card_path: str,
    video_bg_path: str,
    output_path: str,
    duration: float = 30.0,
) -> tuple[str, None]:
    """
    Main path:
      1. Load video bg (10 s), loop to 30 s, crop to 1080×1920
      2. Overlay text card at 80% opacity
      3. Mix bg's original audio + random 30-second sample from audio/
    """
    try:
        from moviepy.audio.AudioClip import CompositeAudioClip
        from moviepy.editor import (
            AudioFileClip,
            CompositeVideoClip,
            ImageClip,
            VideoFileClip,
            concatenate_videoclips,
        )
    except ImportError as exc:
        raise RuntimeError(
            "[video] moviepy is not installed. Run: pip install moviepy\n"
            f"Original error: {exc}"
        ) from exc

    TARGET_W, TARGET_H = 1080, 1920

    print(f"  [video] Video background: {Path(video_bg_path).name}")
    try:
        bg = VideoFileClip(video_bg_path)

        # Loop 10-second bg to fill 30 seconds
        if bg.duration < duration:
            loops = int(duration / bg.duration) + 1
            bg = concatenate_videoclips([bg] * loops)
        bg = bg.subclip(0, duration)

        # Snapshot audio before resize/crop can silently drop it
        bg_audio = bg.audio

        # Resize + center-crop to 9:16
        scale = max(TARGET_W / bg.w, TARGET_H / bg.h)
        bg    = bg.resize(scale)
        x1    = (bg.w - TARGET_W) // 2
        y1    = (bg.h - TARGET_H) // 2
        bg    = bg.crop(x1=x1, y1=y1, x2=x1 + TARGET_W, y2=y1 + TARGET_H)

        card_clip = ImageClip(card_path, ismask=False).set_duration(duration)
        final     = CompositeVideoClip([bg, card_clip])

        # Build audio: bg original sound + random music sample
        audio_tracks = []

        if bg_audio is not None:
            audio_tracks.append(bg_audio)

        audio_name = None
        result = _pick_audio()
        if result:
            music_path, audio_name = result
            try:
                raw       = AudioFileClip(music_path)
                max_start = max(0.0, raw.duration - duration)
                start     = random.uniform(0, max_start)
                music     = raw.subclip(start, start + duration).audio_fadeout(1.5)
                audio_tracks.append(music)
                print(f"  [audio] Sample: {start:.1f}s – {start + duration:.1f}s")
            except Exception as exc:
                print(f"  [video] WARNING: music failed ({exc}) — using bg audio only")

        if audio_tracks:
            mixed = CompositeAudioClip(audio_tracks) if len(audio_tracks) > 1 else audio_tracks[0]
            final = final.set_audio(mixed)
            print(f"  [audio] {len(audio_tracks)} track(s) mixed")

        final.write_videofile(
            output_path,
            fps=OUTPUT_FPS,
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None,
        )
        print(f"  [video] Saved: {output_path}")
        return output_path, audio_name

    except Exception as exc:
        raise RuntimeError(
            f"[video] Video-bg reel failed: {type(exc).__name__}: {exc}"
        ) from exc
