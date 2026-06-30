"""
Waskodigama — Instagram Comedy Reel Pipeline.

Usage:
  python main.py          # run once, then every N hours
  python main.py --once   # run exactly once and exit
  python main.py --dry    # generate everything, skip posting
"""

import json
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
Path("audio").mkdir(exist_ok=True)  # reserved for future audio use

DRY_RUN       = "--dry" in sys.argv
REEL_DURATION = 30.0

# ── Per-gender content config ──────────────────────────────────────────────────
GENDER_CONFIG = {
    "male": {
        "oneliner_file": Path("video/male/one-liners.md"),
        "index_file":    Path("oneliner_index_male.json"),
        "video_dir":     Path("video/male"),
    },
    "female": {
        "oneliner_file": Path("video/female/one-liners.md"),
        "index_file":    Path("oneliner_index_female.json"),
        "video_dir":     Path("video/female"),
    },
}

# ── Category keyword → internal ID (per gender) ───────────────────────────────
MALE_CATEGORY_MAP = {
    "Desi Household":     "desi_household_and_relatives",
    "Creative Breakdown": "creative_breakdown_and_editor",
    "Group Chats":        "group_chats_and_goa_plans",
    "Traffic":            "traffic_and_driving",
    "Dating":             "dating_and_relationships",
    "Online Shopping":    "online_shopping_addiction",
    "Laziness":           "extreme_laziness_and_sleep",
    "Gym":                "gym_diet_and_delusions",
}

FEMALE_CATEGORY_MAP = {
    "Girl Math":  "girl_math_and_shopping",
    "Shopping":   "girl_math_and_shopping",
    "Skincare":   "skincare_and_makeup",
    "Makeup":     "skincare_and_makeup",
    "Besties":    "besties_and_gossip",
    "Dating":     "dating_and_delulu",
    "Delulu":     "dating_and_delulu",
    "Mood":       "mood_swings_and_pms",
    "PMS":        "mood_swings_and_pms",
    "Adulting":   "adulting_and_survival",
}



def _load_oneliners(oneliner_file: Path, category_map: dict) -> dict[int, dict]:
    """Parse the MD file into {number: {"category": str, "text": str}}."""
    if not oneliner_file.exists():
        raise FileNotFoundError(f"One-liner file not found: {oneliner_file}")

    data: dict[int, dict] = {}
    current_category = "general"

    for line in oneliner_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            for keyword, cat_id in category_map.items():
                if keyword in line:
                    current_category = cat_id
                    break
        else:
            m = re.match(r"^(\d+)\.\s+(.+)$", line.strip())
            if m:
                data[int(m.group(1))] = {
                    "category": current_category,
                    "text":     m.group(2).strip(),
                }

    return data


def _get_next_oneliner(
    oneliner_file: Path,
    index_file: Path,
    category_map: dict,
) -> tuple[int, str, str]:
    """Return (number, category, text) — random pick from unused, resets when all done."""
    index_data = {}
    if index_file.exists():
        index_data = json.loads(index_file.read_text())

    used      = set(index_data.get("used", []))
    oneliners = _load_oneliners(oneliner_file, category_map)

    if not oneliners:
        raise RuntimeError(f"No one-liners found in {oneliner_file}")

    all_nums  = list(oneliners.keys())
    remaining = [n for n in all_nums if n not in used]

    if not remaining:
        used = set()
        remaining = all_nums
        print(f"  [oneliner] All done — reshuffling from scratch")

    next_num = random.choice(remaining)
    used.add(next_num)
    index_file.write_text(json.dumps({"used": sorted(used)}))
    entry = oneliners[next_num]
    return next_num, entry["category"], entry["text"]


def _pick_video_bg(video_dir: Path) -> str | None:
    """Pick a random video file from the gender folder."""
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

    gender     = "female"
    cfg     = GENDER_CONFIG[gender]
    cat_map = MALE_CATEGORY_MAP if gender == "male" else FEMALE_CATEGORY_MAP
    print(f"\n{'='*60}")
    print(f"  Waskodigama Comedy Reel Pipeline — {ts}")
    print(f"  Gender : {gender}  |  Dry run: {DRY_RUN}")
    print(f"{'='*60}")

    try:
        # STEP 1 — pick next one-liner for this gender
        print(f"\n[1/4] Getting next one-liner ({gender})...")
        number, category, text = _get_next_oneliner(
            cfg["oneliner_file"], cfg["index_file"], cat_map
        )
        print(f"  #{number} [{category}]")
        print(f"  Text: {text[:100]}")

        # STEP 2 — generate caption + hashtags via Groq
        print("\n[2/4] Generating caption via Groq...")
        caption_data = generate_caption_for_oneliner(text, category, number, gender)
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
        # Caption: hook → CTA → 9 hashtags (3 niche + 3 mid + 3 broad) → #N
        ig_caption = (
            f"{hook}\n\n"
            f"{cta}\n\n"
            f"{niche_ht} {mid_ht} {broad_ht}\n\n"
            f"#{number}"
        )
        reel_path = str(OUTPUT_DIR / f"reel_{run_id}.mp4")
        video_bg  = _pick_video_bg(cfg["video_dir"])

        print("\n[4/4] Composing Reel video...")
        if video_bg:
            reel_path, _ = compose_reel_with_video_bg(
                card_path, video_bg, reel_path, duration=REEL_DURATION
            )
        else:
            print("  No video background found — using gradient card only")
            reel_path, _ = compose_reel([card_path], reel_path, duration=REEL_DURATION)

        if DRY_RUN:
            print("\n  DRY RUN — skipping post")
            print(f"  Caption preview:\n{ig_caption}")
        else:
            print("  Posting Reel to Instagram...")
            url = post_reel(reel_path, ig_caption)
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
