"""
Polls Telegram for a new message from the authorized chat and, if found,
exposes it as a GitHub Actions output so the workflow's next step can post
it directly via `main.py --text "..."` instead of picking a random one-liner.

Message format sent to the bot:
  <any text>                → posted under the default (first) category
  <category>: <any text>    → posted under that specific category

Run manually:  python telegram_listener.py
"""

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(override=False)

BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID", "").strip()
OFFSET_FILE = Path("telegram_offset.json")


def _load_last_update_id() -> int:
    if OFFSET_FILE.exists():
        return json.loads(OFFSET_FILE.read_text()).get("last_update_id", 0)
    return 0


def _save_last_update_id(update_id: int) -> None:
    OFFSET_FILE.write_text(json.dumps({"last_update_id": update_id}))


def _write_github_output(has_message: bool, message: str = "") -> None:
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if not gh_output:
        return
    with open(gh_output, "a", encoding="utf-8") as f:
        f.write(f"has_message={'true' if has_message else 'false'}\n")
        f.write("message<<TELEGRAM_EOF\n")
        f.write(f"{message}\n")
        f.write("TELEGRAM_EOF\n")


def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("[telegram] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skipping")
        _write_github_output(False)
        return

    last_id = _load_last_update_id()
    resp = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
        params={"offset": last_id + 1, "timeout": 0},
        timeout=15,
    )
    resp.raise_for_status()
    updates = resp.json().get("result", [])

    if not updates:
        print("[telegram] No new updates")
        _write_github_output(False)
        return

    newest_id   = last_id
    chosen_text = None

    for update in updates:
        newest_id = max(newest_id, update["update_id"])
        msg = update.get("message") or update.get("channel_post")
        if not msg:
            continue
        if str(msg.get("chat", {}).get("id")) != str(CHAT_ID):
            continue
        text = (msg.get("text") or "").strip()
        if text:
            chosen_text = text  # last matching message in this batch wins

    _save_last_update_id(newest_id)

    if chosen_text:
        print(f"[telegram] New message: {chosen_text[:80]}")
        _write_github_output(True, chosen_text)
    else:
        print("[telegram] Updates seen but none from the authorized chat")
        _write_github_output(False)


if __name__ == "__main__":
    main()
