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

OUTPUT_FPS      = 30
AUDIO_NO_REPEAT = 3


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
        pool = tracks  # all recently used — reset
    chosen = random.choice(pool)
    _save_audio_history(audio_dir, chosen.name)
    print(f"  [audio] Track: {chosen.name}")
    return str(chosen), chosen.stem


def _make_gradient_bg(width: int = 1080, height: int = 1920) -> "PIL.Image.Image":
    """Create a vertical gradient background image."""
    import PIL.Image as PILImage
    import PIL.ImageDraw as PILImageDraw
    top    = (30, 20, 50)    # deep purple
    bottom = (90, 40, 120)   # violet
    img    = PILImage.new("RGB", (width, height))
    draw   = PILImageDraw.Draw(img)
    for y in range(height):
        t = y / height
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def compose_reel(
    image_paths: list[str],
    output_path: str,
    audio_dir: Path,
    duration: float | None = None,
) -> tuple[str, None]:
    """Fallback: gradient bg + text card + random audio (no video bg)."""
    try:
        from moviepy.editor import AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips
    except ImportError as exc:
        raise RuntimeError(
            "[video] moviepy is not installed. Run: pip install moviepy\n"
            f"Original error: {exc}"
        ) from exc

    slide_dur = duration if duration is not None else 3.0
    print(f"  [video] Composing {len(image_paths)} slide(s) × {slide_dur}s each (gradient bg)...")
    try:
        import tempfile, os
        # Save gradient bg as a temp image and composite with each card
        grad = _make_gradient_bg()
        tmp  = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        grad.save(tmp.name)
        tmp.close()

        clips = []
        for p in image_paths:
            bg   = ImageClip(tmp.name).set_duration(slide_dur)
            card = ImageClip(p).set_duration(slide_dur)
            clips.append(CompositeVideoClip([bg, card]))
        os.unlink(tmp.name)

        video  = concatenate_videoclips(clips, method="compose")
        target = video.duration

        audio_name = None
        result = _pick_audio(audio_dir)
        if result:
            audio_path, audio_name = result
            try:
                raw       = AudioFileClip(audio_path)
                use_dur   = min(target, raw.duration)
                max_start = max(0.0, raw.duration - use_dur)
                start     = random.uniform(0, max_start)
                music     = raw.subclip(start, start + use_dur).audio_fadeout(1.5)
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


def _transcode_to_h264(src: str) -> str:
    """Re-encode video to H.264/AAC MP4 using ffmpeg subprocess before MoviePy reads it."""
    import subprocess, tempfile, os
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", src,
         "-c:v", "libx264", "-preset", "fast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k",
         tmp.name],
        capture_output=True
    )
    if result.returncode == 0:
        print(f"  [video] Transcoded to H.264: {Path(src).name}")
        return tmp.name
    os.unlink(tmp.name)
    raise RuntimeError(
        f"ffmpeg transcode failed for {src}:\n{result.stderr.decode()[-400:]}"
    )


def compose_reel_with_video_bg(
    card_path: str,
    video_bg_path: str,
    output_path: str,
    audio_dir: Path,
    duration: float = 30.0,
) -> tuple[str, None]:
    """
    Main path:
      1. Transcode video bg to H.264 (handles HEVC/any codec)
      2. Load, loop to 30 s, crop to 1080×1920
      3. Overlay text card at 80% opacity
      4. Mix bg's original audio + random 30-second sample from the category's audio dir
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
        from moviepy.video.fx.all import time_mirror
    except ImportError as exc:
        raise RuntimeError(
            "[video] moviepy is not installed. Run: pip install moviepy\n"
            f"Original error: {exc}"
        ) from exc

    TARGET_W, TARGET_H = 1080, 1920

    print(f"  [video] Video background: {Path(video_bg_path).name}")
    tmp_path = None
    try:
        tmp_path = _transcode_to_h264(video_bg_path)
        bg = VideoFileClip(tmp_path)

        # Ping-pong (boomerang) loop to fill the reel duration: forward, then
        # reversed, then forward, etc. Always seamless at each loop boundary
        # (frame + audio) since a reversed clip always returns exactly to its
        # starting frame — unlike a straight repeat, which jump-cuts if the
        # clip wasn't authored as a perfect loop. time_mirror() reverses both
        # the video and its audio track together, so they stay in sync.
        if bg.duration < duration:
            forward, backward = bg, bg.fx(time_mirror)
            segments, total, use_forward = [], 0.0, True
            while total < duration:
                segments.append(forward if use_forward else backward)
                total += bg.duration
                use_forward = not use_forward
            bg = concatenate_videoclips(segments)
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
        result = _pick_audio(audio_dir)
        if result:
            music_path, audio_name = result
            try:
                raw       = AudioFileClip(music_path)
                use_dur   = min(duration, raw.duration)
                max_start = max(0.0, raw.duration - use_dur)
                start     = random.uniform(0, max_start)
                music     = raw.subclip(start, start + use_dur).audio_fadeout(1.5)
                audio_tracks.append(music)
                print(f"  [audio] Sample: {start:.1f}s – {start + use_dur:.1f}s")
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
    finally:
        import os
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
