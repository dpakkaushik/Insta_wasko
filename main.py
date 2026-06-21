"""
Instagram Reel Pipeline — main entry point.

Usage:
  python main.py          # run once now, then every N hours
  python main.py --once   # run exactly once and exit
  python main.py --dry    # generate everything, skip posting
"""

import json
import random
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import schedule
from PIL import Image

from config import POST_INTERVAL_HOURS
from gemini_processor import generate_carousel
from image_composer import compose_card, make_gradient_bg
from video_composer import compose_reel
from instagram_poster import post_reel

OUTPUT_DIR   = Path("output")
TEMPLATE_DIR = Path("templates")
OUTPUT_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)

DRY_RUN = "--dry" in sys.argv

REEL_DURATION = 10.0   # seconds — single image Reel


TOTAL_MOODS       = 10
MOOD_HISTORY      = Path("mood_history.json")
MOOD_NO_REPEAT    = 3
TEMPLATE_HISTORY  = Path("template_history.json")
TEMPLATE_NO_REPEAT = 3


def _load_mood_history() -> list[int]:
    if MOOD_HISTORY.exists():
        return json.loads(MOOD_HISTORY.read_text())
    return []


def _save_mood_history(mood: int) -> None:
    history = _load_mood_history()
    history.insert(0, mood)
    MOOD_HISTORY.write_text(json.dumps(history[:MOOD_NO_REPEAT]))


def _load_template_history() -> list[str]:
    if TEMPLATE_HISTORY.exists():
        return json.loads(TEMPLATE_HISTORY.read_text())
    return []


def _save_template_history(name: str) -> None:
    history = _load_template_history()
    history.insert(0, name)
    TEMPLATE_HISTORY.write_text(json.dumps(history[:TEMPLATE_NO_REPEAT]))


def _pick_mood() -> int:
    history = _load_mood_history()
    excluded = set(history[:MOOD_NO_REPEAT])
    pool = [m for m in range(1, TOTAL_MOODS + 1) if m not in excluded]
    if not pool:
        pool = list(range(1, TOTAL_MOODS + 1))
    mood = random.choice(pool)
    _save_mood_history(mood)
    return mood


def _pick_template(mood_number: int) -> Image.Image:
    """Pick a random template image. Naming: MMCC.ext where MM=mood, CC=count (e.g. 0101.png)."""
    prefix = f"{mood_number:02d}"
    candidates = (
        list(TEMPLATE_DIR.glob(f"{prefix}*.jpg"))
        + list(TEMPLATE_DIR.glob(f"{prefix}*.jpeg"))
        + list(TEMPLATE_DIR.glob(f"{prefix}*.png"))
    )
    if not candidates:
        # Fall back to any image in templates/
        candidates = (
            list(TEMPLATE_DIR.glob("*.jpg"))
            + list(TEMPLATE_DIR.glob("*.jpeg"))
            + list(TEMPLATE_DIR.glob("*.png"))
        )
    if not candidates:
        print(f"  No templates found — using gradient background")
        return make_gradient_bg(mood_number)

    history  = _load_template_history()
    excluded = set(history[:TEMPLATE_NO_REPEAT])
    pool     = [c for c in candidates if c.name not in excluded]
    if not pool:
        pool = candidates
    chosen = random.choice(pool)
    _save_template_history(chosen.name)
    print(f"  Template : {chosen.name}")
    return Image.open(chosen).convert("RGB")


def run_pipeline() -> None:
    ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_id  = datetime.now().strftime("%Y%m%d_%H%M%S")
    mood_number = _pick_mood()

    print(f"\n{'='*60}")
    print(f"  Instagram Reel Pipeline — {ts}")
    print(f"  Mood: #{mood_number}  |  Dry run: {DRY_RUN}")
    print(f"{'='*60}")

    try:
        # ── STEP 1: Pick template + generate quote ────────────────────
        print(f"\n[1/4] Picking Mood {mood_number} template...")
        bg_image = _pick_template(mood_number)

        print("\n[2/4] Generating quote...")
        data = generate_carousel(mood_number)
        quote = data["quote"]
        print(f"  Mood #{mood_number} : {data.get('mood_name', '')}")
        print(f"  Quote    : {quote}")

        # ── STEP 3: Compose card ──────────────────────────────────────
        print("\n[3/4] Composing card...")
        card = compose_card(
            quote       = quote,
            mood_number = mood_number,
            bg_image    = bg_image,
        )
        card_path = str(OUTPUT_DIR / f"card_{run_id}.jpg")
        card.save(card_path, "JPEG", quality=95)
        print(f"  Saved: {Path(card_path).name}")

        # ── STEP 4: Compose Reel + post ──────────────────────────────
        ig_caption = f"{data['caption']}\n\n{data['hashtags']}"
        reel_path  = str(OUTPUT_DIR / f"reel_{run_id}.mp4")

        print("\n[4/4] Composing Reel video...")
        reel_path, track_name = compose_reel([card_path], reel_path, duration=REEL_DURATION)

        if DRY_RUN:
            print("\n  DRY RUN — skipping post")
            print(f"  Caption preview: {ig_caption[:200]}")
            print(f"  Track name    : {track_name}")
            print(f"  Output: {OUTPUT_DIR.resolve()}")
        else:
            print("  Posting Reel to Instagram...")
            url = post_reel(reel_path, ig_caption, audio_name=track_name)
            print(f"\n  POSTED: {url}")

        print(f"\n{'='*60}")
        print(f"  Pipeline complete — {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}\n")

    except Exception as exc:
        print(f"\n{'!'*60}")
        print(f"  PIPELINE FAILED")
        print(f"  Error type : {type(exc).__name__}")
        print(f"  Message    : {exc}")
        print(f"{'!'*60}")
        print(traceback.format_exc())
        print("  Run aborted — no post was made.\n")
        sys.exit(1)


if __name__ == "__main__":
    if "--once" in sys.argv or "--dry" in sys.argv:
        run_pipeline()
    else:
        print(f"[scheduler] Running now, then every {POST_INTERVAL_HOURS} hour(s). Ctrl+C to stop.\n")
        run_pipeline()
        schedule.every(POST_INTERVAL_HOURS).hours.do(run_pipeline)
        while True:
            schedule.run_pending()
            time.sleep(60)
