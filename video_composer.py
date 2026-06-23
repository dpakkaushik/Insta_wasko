"""
Combine 4 slide JPEGs + an optional music track into a single MP4 Reel.
Each slide is shown for SLIDE_DURATION seconds. Music is trimmed to fit
and faded out in the last second. If no music file is found the Reel is
posted silent — the run is NOT aborted for missing music.
"""

import json
import random
from pathlib import Path

SLIDE_DURATION      = 3.0
AUDIO_DIR           = Path("audio")
OUTPUT_FPS          = 30
AUDIO_HISTORY_FILE  = Path("audio_history.json")
AUDIO_NO_REPEAT     = 3


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
        print("  [video] audio/ folder not found — posting silent")
        return None
    tracks = (
        list(AUDIO_DIR.glob("*.mp3"))
        + list(AUDIO_DIR.glob("*.m4a"))
        + list(AUDIO_DIR.glob("*.wav"))
    )
    if not tracks:
        print("  [video] No audio files in audio/ — posting silent")
        return None
    history  = _load_audio_history()
    excluded = set(history[:AUDIO_NO_REPEAT])
    pool     = [t for t in tracks if t.name not in excluded]
    if not pool:
        pool = tracks
    chosen = random.choice(pool)
    _save_audio_history(chosen.name)
    print(f"  [video] Audio: {chosen.name}")
    return str(chosen)


def compose_reel(image_paths: list[str], output_path: str, duration: float | None = None) -> tuple[str, str | None]:
    """
    Build output_path MP4 from image_paths.
    Returns (output_path, track_name_without_extension) so caller can use track name for IG audio.
    """
    try:
        from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
    except ImportError as exc:
        raise RuntimeError(
            "[video] moviepy is not installed. Run: pip install moviepy\n"
            f"Original error: {exc}"
        ) from exc

    slide_dur  = duration if duration is not None else SLIDE_DURATION
    track_name = None
    print(f"  [video] Composing {len(image_paths)} slide(s) × {slide_dur}s each...")
    try:
        clips = [ImageClip(p).set_duration(slide_dur) for p in image_paths]
        video = concatenate_videoclips(clips, method="compose")

        audio_path = _pick_audio()
        if audio_path:
            try:
                from moviepy.audio.AudioClip import concatenate_audioclips
                audio = AudioFileClip(audio_path)
                if audio.duration < video.duration:
                    loops = int(video.duration / audio.duration) + 1
                    audio = concatenate_audioclips([audio] * loops)
                audio = audio.subclip(0, video.duration).audio_fadeout(1.0)
                video = video.set_audio(audio)
                track_name = Path(audio_path).stem  # filename without extension
            except Exception as exc:
                print(f"  [video] WARNING: Could not load audio ({exc}) — posting silent")

        video.write_videofile(
            output_path,
            fps=OUTPUT_FPS,
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None,
        )
        print(f"  [video] Saved: {output_path}")
        return output_path, track_name

    except Exception as exc:
        raise RuntimeError(
            f"[video] Reel composition failed: {type(exc).__name__}: {exc}\n"
            "Check that ffmpeg is installed and all slide images exist."
        ) from exc
