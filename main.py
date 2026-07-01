"""
Waskodigama — Instagram Comedy Reel Pipeline.

Usage:
  python main.py                    # run once, then every N hours
  python main.py --once             # run exactly once and exit
  python main.py --dry              # generate everything, skip posting
  python main.py --text "..."       # post this exact text instead of picking randomly
                                     # prefix with "category: " to target a category,
                                     # e.g. --text "annoyed: kal se diet start karungi"
"""

import os
import random
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import schedule

sys.stdout.reconfigure(encoding='utf-8')

from config import POST_INTERVAL_HOURS
from caption_generator import generate_caption_for_oneliner
from image_composer import compose_card
from video_composer import compose_reel, compose_reel_with_video_bg
from instagram_poster import post_reel

OUTPUT_DIR = Path("output")

OUTPUT_DIR.mkdir(exist_ok=True)

DRY_RUN       = "--dry" in sys.argv
REEL_DURATION = 30.0

# ── Content categories — girl-only content, one category per content bank ──────
# Add every category here as it's created, whether or not it's live yet.
CATEGORY_CONFIG = {
    "annoyed": {
        "oneliner_file": Path("content/annoyed_one_liners.txt"),
        "used_file":     Path("content/annoyed_one_liners_used.txt"),
        "video_dir":     Path("video/annoyed"),
        "audio_dir":     Path("audio/annoyed"),
    },
    "swag": {
        "oneliner_file": Path("content/swag_one_liners.txt"),
        "used_file":     Path("content/swag_one_liners_used.txt"),
        "video_dir":     Path("video/swag"),
        "audio_dir":     Path("audio/swag"),
    },
    "savage": {
        "oneliner_file": Path("content/savage_one_liners.txt"),
        "used_file":     Path("content/savage_one_liners_used.txt"),
        "video_dir":     Path("video/savage"),
        "audio_dir":     Path("audio/savage"),
    },
}

# Categories the random picker (and Telegram "category: " prefix) can actually
# choose from. A category can exist in CATEGORY_CONFIG before its video/audio
# is ready — just don't list it here until it should go live.
ACTIVE_CATEGORIES = ["annoyed", "swag"]

# Relative share of scheduled posts per category. Categories not listed here
# default to weight 1. Only applies to the random picker — Telegram's
# "category: " override always posts to the category you name regardless of
# its weight.
CATEGORY_WEIGHTS = {
    "annoyed": 80,
    "swag":    20,
}

for _cfg in CATEGORY_CONFIG.values():
    _cfg["video_dir"].mkdir(parents=True, exist_ok=True)
    _cfg["audio_dir"].mkdir(parents=True, exist_ok=True)
    _cfg["oneliner_file"].parent.mkdir(parents=True, exist_ok=True)


def _get_arg_value(flag: str) -> str | None:
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


# Manual override — e.g. from the Telegram listener workflow. Skips the random
# picker and posts this exact text instead. Optionally prefixed "category: "
# to target a specific active category; otherwise falls back to the first
# active category.
CUSTOM_TEXT = (os.environ.get("CUSTOM_TEXT", "").strip()) or _get_arg_value("--text")


def _resolve_custom_text(raw_text: str) -> tuple[str, str]:
    """Parse an optional "category: text" prefix out of a manual override."""
    match = re.match(r"^\s*([a-zA-Z_]+)\s*:\s*(.+)$", raw_text, re.DOTALL)
    if match and match.group(1).lower() in ACTIVE_CATEGORIES:
        return match.group(1).lower(), match.group(2).strip()
    return ACTIVE_CATEGORIES[0], raw_text.strip()


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _get_next_oneliner(oneliner_file: Path, used_file: Path) -> str:
    """Pick a random one-liner, move it from oneliner_file to used_file. Resets when exhausted."""
    remaining = _read_lines(oneliner_file)

    if not remaining:
        remaining = _read_lines(used_file)
        if not remaining:
            raise RuntimeError(f"No one-liners found in {oneliner_file} or {used_file}")
        used_file.write_text("", encoding="utf-8")
        print("  [oneliner] All done — reshuffling from scratch")

    chosen = random.choice(remaining)
    remaining.remove(chosen)

    oneliner_file.write_text(
        "\n".join(remaining) + ("\n" if remaining else ""), encoding="utf-8"
    )
    with used_file.open("a", encoding="utf-8") as f:
        f.write(chosen + "\n")

    return chosen


def _pick_video_bg(video_dir: Path) -> str | None:
    """Pick a random video file from the category folder."""
    if not video_dir.exists():
        return None
    vids = [
        v for v in video_dir.iterdir()
        if v.suffix.lower() in (".mp4", ".mov", ".avi", ".webm")
    ]
    if not vids:
        return None
    chosen = random.choice(vids)
    print(f"  [video] Background: {chosen.name}")
    return str(chosen)


def run_pipeline() -> None:
    ts     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    if CUSTOM_TEXT:
        category, text = _resolve_custom_text(CUSTOM_TEXT)
    else:
        weights  = [CATEGORY_WEIGHTS.get(c, 1) for c in ACTIVE_CATEGORIES]
        category = random.choices(ACTIVE_CATEGORIES, weights=weights, k=1)[0]
        text     = None  # picked in STEP 1 below
    cfg = CATEGORY_CONFIG[category]

    print(f"\n{'='*60}")
    print(f"  Waskodigama Comedy Reel Pipeline — {ts}")
    mode = "custom text" if CUSTOM_TEXT else "auto"
    print(f"  Category : {category}  |  Mode: {mode}  |  Dry run: {DRY_RUN}")
    print(f"{'='*60}")

    try:
        # STEP 1 — custom text overrides the random picker; otherwise pick next one-liner
        if CUSTOM_TEXT:
            print(f"\n[1/4] Using custom text ({category})...")
        else:
            print(f"\n[1/4] Getting next one-liner ({category})...")
            text = _get_next_oneliner(cfg["oneliner_file"], cfg["used_file"])
        print(f"  Text: {text[:100]}")

        # STEP 2 — generate caption + hashtags via Groq
        print("\n[2/4] Generating caption via Groq...")
        caption_data = generate_caption_for_oneliner(text, category)
        hook     = caption_data.get("hook", "")
        cta      = caption_data.get("cta", "")
        niche_ht = caption_data.get("niche_hashtags", "")
        mid_ht   = caption_data.get("mid_hashtags", "")
        broad_ht = caption_data.get("broad_hashtags", "")
        print(f"  Hook    : {hook[:80]}")
        print(f"  CTA     : {cta[:60]}")
        print(f"  Hashtags: {niche_ht} {mid_ht} {broad_ht}")

        # STEP 3 — render text as transparent PNG overlay
        print("\n[3/4] Composing text overlay...")
        card      = compose_card(quote=text, font_color=(0, 0, 0))
        card_path = str(OUTPUT_DIR / f"card_{run_id}.png")
        card.save(card_path, "PNG")
        print(f"  Saved: {Path(card_path).name}")

        # STEP 4 — compose reel (video bg if available) + post
        # Caption: hook → CTA → 9 hashtags (3 niche + 3 mid + 3 broad)
        ig_caption = (
            f"{hook}\n\n"
            f"{cta}\n\n"
            f"{niche_ht} {mid_ht} {broad_ht}"
        )
        reel_path = str(OUTPUT_DIR / f"reel_{run_id}.mp4")
        video_bg  = _pick_video_bg(cfg["video_dir"])

        print("\n[4/4] Composing Reel video...")
        if video_bg:
            try:
                reel_path, audio_name = compose_reel_with_video_bg(
                    card_path, video_bg, reel_path, cfg["audio_dir"], duration=REEL_DURATION
                )
            except RuntimeError as e:
                print(f"  ⚠️  Video background failed ({e}) — falling back to gradient")
                reel_path, audio_name = compose_reel(
                    [card_path], reel_path, cfg["audio_dir"], duration=REEL_DURATION
                )
        else:
            print("  No video background found — using gradient card only")
            reel_path, audio_name = compose_reel(
                [card_path], reel_path, cfg["audio_dir"], duration=REEL_DURATION
            )

        if DRY_RUN:
            print("\n  DRY RUN — skipping post")
            print(f"  Caption preview:\n{ig_caption}")
        else:
            print("  Posting Reel to Instagram...")
            url = post_reel(reel_path, ig_caption, audio_name=audio_name)
            print(f"\n  POSTED: {url}")
            Path(card_path).unlink(missing_ok=True)
            Path(reel_path).unlink(missing_ok=True)
            print("  Cleaned up local files.")

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
