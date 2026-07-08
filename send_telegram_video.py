"""
Send the newest generated reel in output/ back to the configured Telegram chat.

Used by the Telegram preview GitHub Action after `main.py --dry --once`.
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(override=False)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
VIDEO_PATH = os.getenv("TELEGRAM_VIDEO_PATH", "").strip()


def _latest_reel() -> Path:
    if VIDEO_PATH:
        path = Path(VIDEO_PATH)
        if path.exists():
            return path
        raise FileNotFoundError(f"TELEGRAM_VIDEO_PATH does not exist: {path}")

    reels = sorted(
        Path("output").glob("reel_*.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not reels:
        raise FileNotFoundError("No generated reel found under output/reel_*.mp4")
    return reels[0]


def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

    reel_path = _latest_reel()
    print(f"[telegram] Sending preview video: {reel_path}")

    with reel_path.open("rb") as video_file:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
            data={
                "chat_id": CHAT_ID,
                "caption": "Preview video generated. Instagram posting was skipped.",
                "supports_streaming": "true",
            },
            files={"video": (reel_path.name, video_file, "video/mp4")},
            timeout=120,
        )
    response.raise_for_status()
    print("[telegram] Preview video sent")


if __name__ == "__main__":
    main()
