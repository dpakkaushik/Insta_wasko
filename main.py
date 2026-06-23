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

sys.stdout.reconfigure(encoding='utf-8')
import traceback
from datetime import datetime
from pathlib import Path

import io

import cloudinary
import cloudinary.api
import requests
import schedule
from PIL import Image

from config import (
    POST_INTERVAL_HOURS,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET,
)
from gemini_processor import generate_carousel
from image_composer import compose_card, make_gradient_bg
from video_composer import compose_reel
from instagram_poster import post_reel

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
)

OUTPUT_DIR = Path("output")
AUDIO_DIR  = Path("audio")
OUTPUT_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)

DRY_RUN = "--dry" in sys.argv

REEL_DURATION = 30.0

# ── ALL 10 categories (reference list — do not remove) ────────────────────────
ALL_CATEGORIES = [
    "career_and_burnout",
    "comparison_and_timelines",
    "heartbreak_and_letting_go",
    "loneliness_and_isolation",
    "overthinking_and_anxiety",
    "failure_and_self_doubt",
    "discipline_and_motivation",
    "family_and_expectations",
    "grief_and_healing",
    "ego_and_patience",
]

# ── ACTIVE genders — edit as you add images ───────────────────────────────────
# Add "girl" once you have images in templates/<category>/girl/<light|dark>/
ACTIVE_GENDERS = [
    "boy",
    # "girl",
]

# ── ACTIVE categories — edit this list as you add templates + prompts ─────────
# Add a category here ONLY when you have:
#   1. At least one image in templates/<category>/<gender>/<light|dark>/
#   2. The corresponding prompts/<category>.txt file (already created for all 10)
ACTIVE_CATEGORIES = [
    "overthinking_and_anxiety",
    "heartbreak_and_letting_go",
    "career_and_burnout",
    "comparison_and_timelines",
    # Add more as you upload images to Cloudinary:
    # "loneliness_and_isolation",
    # "failure_and_self_doubt",
    # "discipline_and_motivation",
    # "family_and_expectations",
    # "grief_and_healing",
    # "ego_and_patience",
]

# ── Language mix — 60% English, 40% Hindi ────────────────────────────────────
LANGUAGES        = ["english", "hindi"]
LANGUAGE_WEIGHTS = [80, 20]

# ── One Krishna/devotional tag always appended (rotates to stay fresh) ────────
KRISHNA_TAG_POOL = [
    "#Krishna",
    "#BhagavadGita",
    "#LordKrishna",
    "#KrishnaQuotes",
    "#GitaQuotes",
    "#KrishnaWisdom",
    "#HareKrishna",
]

CATEGORY_HISTORY    = Path("category_history.json")
CATEGORY_NO_REPEAT  = 1   # just avoid repeating the same category back-to-back
TEMPLATE_HISTORY    = Path("template_history.json")
TEMPLATE_NO_REPEAT  = 5   # avoid reusing the same image for 5 posts


def _load_category_history() -> list[str]:
    if CATEGORY_HISTORY.exists():
        return json.loads(CATEGORY_HISTORY.read_text())
    return []


def _save_category_history(category: str) -> None:
    history = _load_category_history()
    history.insert(0, category)
    CATEGORY_HISTORY.write_text(json.dumps(history[:CATEGORY_NO_REPEAT]))


def _load_template_history() -> list[str]:
    if TEMPLATE_HISTORY.exists():
        return json.loads(TEMPLATE_HISTORY.read_text())
    return []


def _save_template_history(name: str) -> None:
    history = _load_template_history()
    history.insert(0, name)
    TEMPLATE_HISTORY.write_text(json.dumps(history[:TEMPLATE_NO_REPEAT]))


def _pick_category() -> str:
    if not ACTIVE_CATEGORIES:
        raise RuntimeError(
            "ACTIVE_CATEGORIES is empty. Add at least one category to main.py."
        )
    history  = _load_category_history()
    excluded = set(history[:CATEGORY_NO_REPEAT])
    pool     = [c for c in ACTIVE_CATEGORIES if c not in excluded]
    if not pool:
        pool = list(ACTIVE_CATEGORIES)
    category = random.choice(pool)
    _save_category_history(category)
    return category


def _list_cloudinary(prefix: str) -> list[dict]:
    """Return all image resources under a Cloudinary prefix."""
    resources = []
    next_cursor = None
    while True:
        kwargs = {"type": "upload", "resource_type": "image",
                  "prefix": prefix, "max_results": 500}
        if next_cursor:
            kwargs["next_cursor"] = next_cursor
        result = cloudinary.api.resources(**kwargs)
        resources.extend(result.get("resources", []))
        next_cursor = result.get("next_cursor")
        if not next_cursor:
            break
    return resources


def _pick_template(category: str, gender: str, lighting: str) -> Image.Image:
    """Fetch a random template image from Cloudinary."""
    prefix = f"insta_radha/{category}/{gender}/{lighting}/"
    candidates = _list_cloudinary(prefix)

    if not candidates:
        # Widen to any lighting under this category/gender
        candidates = _list_cloudinary(f"insta_radha/{category}/{gender}/")

    if not candidates:
        print(f"  No templates on Cloudinary for {category}/{gender} - using gradient")
        return make_gradient_bg()

    history  = _load_template_history()
    excluded = set(history[:TEMPLATE_NO_REPEAT])
    pool     = [r for r in candidates if r["public_id"] not in excluded]
    if not pool:
        pool = candidates

    chosen = random.choice(pool)
    _save_template_history(chosen["public_id"])
    print(f"  Template : {chosen['public_id'].split('/')[-1]}")

    resp = requests.get(chosen["secure_url"], timeout=30)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def run_pipeline() -> None:
    ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_id  = datetime.now().strftime("%Y%m%d_%H%M%S")

    if not ACTIVE_GENDERS:
        raise RuntimeError("ACTIVE_GENDERS is empty. Add 'boy' or 'girl' to main.py.")
    gender   = random.choice(ACTIVE_GENDERS)
    category = _pick_category()
    lighting = random.choice(["light", "dark"])
    language = random.choices(LANGUAGES, weights=LANGUAGE_WEIGHTS, k=1)[0]
    font_color = (30, 30, 30) if lighting == "light" else (245, 245, 245)

    print(f"\n{'='*60}")
    print(f"  Instagram Reel Pipeline - {ts}")
    print(f"  Category : {category}")
    print(f"  Gender   : {gender}  |  Lighting: {lighting}  |  Language: {language}")
    print(f"  Dry run  : {DRY_RUN}")
    print(f"{'='*60}")

    try:
        # STEP 1: Pick template
        print(f"\n[1/4] Picking template ({category}/{gender}/{lighting})...")
        bg_image = _pick_template(category, gender, lighting)

        # STEP 2: Generate Q&A dialogue
        print("\n[2/4] Generating Krishna dialogue...")
        data = generate_carousel(category, gender, language)
        quote = data["quote"]
        print(f"  Category       : {data.get('category', '')}")
        print(f"  Quote          : {quote.replace(chr(10), ' | ')}")
        print(f"  Caption        : {data.get('caption', '')}")
        print(f"  Hashtags       : {data.get('hashtags', '')}")
        print(f"  Search keyword : {data.get('search_keyword', '')}")
        print(f"  Alt text       : {data.get('alt_text', '')}")

        # STEP 3: Compose card
        print("\n[3/4] Composing card...")
        card = compose_card(
            quote      = quote,
            font_color = font_color,
            bg_image   = bg_image,
        )
        card_path = str(OUTPUT_DIR / f"card_{run_id}.jpg")
        card.save(card_path, "JPEG", quality=95)
        print(f"  Saved: {Path(card_path).name}")

        # STEP 4: Compose Reel + post
        krishna_tag = random.choice(KRISHNA_TAG_POOL)
        ig_caption = f"{data['caption']}\n\n{data['hashtags']} {krishna_tag}"
        reel_path  = str(OUTPUT_DIR / f"reel_{run_id}.mp4")

        print("\n[4/4] Composing Reel video...")
        reel_path, track_name = compose_reel([card_path], reel_path, duration=REEL_DURATION)

        if DRY_RUN:
            print("\n  DRY RUN - skipping post")
            print(f"  Caption preview: {ig_caption[:200]}")
            print(f"  Track name     : {track_name}")
        else:
            print("  Posting Reel to Instagram...")
            url = post_reel(reel_path, ig_caption, audio_name=track_name)
            print(f"\n  POSTED: {url}")
            Path(card_path).unlink(missing_ok=True)
            Path(reel_path).unlink(missing_ok=True)
            print("  Cleaned up local files.")

        print(f"\n{'='*60}")
        print(f"  Pipeline complete - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}\n")

    except Exception as exc:
        print(f"\n{'!'*60}")
        print(f"  PIPELINE FAILED")
        print(f"  Error type : {type(exc).__name__}")
        print(f"  Message    : {exc}")
        print(f"{'!'*60}")
        print(traceback.format_exc())
        print("  Run aborted - no post was made.\n")
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
