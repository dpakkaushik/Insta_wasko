# Waskodigama — Instagram Comedy Reel Pipeline

## What This Does
Posts Hinglish comedy one-liners as Instagram Reels, automatically, on a schedule.
Girl-only content, organized into categories (currently just `annoyed`; more will be added over time), each with its own content bank and video backgrounds.

## Architecture

```
random category → one-liner (picked + moved to "used") → Groq (caption) → card → video bg overlay → Instagram
```

1. `main.py` picks a category at random from `CATEGORY_CONFIG` (currently only `annoyed`)
2. Picks a random unused one-liner from `content/{category}_one_liners.txt`, then moves it to `content/{category}_one_liners_used.txt` so it won't repeat until the bank is exhausted
3. Groq generates a short Hinglish caption + hashtags
4. The one-liner text is rendered on a gradient background card (1080×1920 JPEG)
5. Card is composited over a video background from `video/{category}/` (if any MP4s exist)
6. Final MP4 reel is posted to Instagram with caption + hashtags

## Content Banks

Each category is a plain-text file, one one-liner per line (no numbering, no headers).

### Annoyed (`content/annoyed_one_liners.txt`)
Girl-life annoyances — shopping delusions, skincare/makeup chaos, bestie gossip, dating/delulu, mood swings & overthinking, adulting struggles.

More categories will be added the same way: a new entry in `CATEGORY_CONFIG` in `main.py`, plus its own `content/{category}_one_liners.txt` + `video/{category}/`.

## Used-Content Tracking
- `content/{category}_one_liners.txt` — pool of one-liners not yet posted
- `content/{category}_one_liners_used.txt` — one-liners already posted
- Each pick removes one line from the first file and appends it to the second
- When the unused pool is empty, everything in the used file resets back into the pool (reshuffle) — no manual index files to manage

## Video Backgrounds
Drop MP4/MOV files into `video/{category}/` (e.g. `video/annoyed/`).
- Pipeline picks a random video from the category's folder each run
- Videos are looped or trimmed to fill the 30-second reel duration
- Resized/cropped to 9:16 (1080×1920) automatically
- Text card is overlaid at 80% opacity so background shows through
- If no video files exist, falls back to pure gradient background
- Note: if the background video itself has an embedded audio track, that plays mixed together with the instrumental track from `audio/` — this is intentional, not a bug

## Audio
Drop MP3/M4A/WAV files into `audio/`. Picked randomly (no repeat for 3 runs).

## Running

```bash
python main.py                  # run now, then every N hours (set POST_INTERVAL_HOURS in .env)
python main.py --once           # run exactly once
python main.py --dry            # generate card + reel, skip posting (for testing)
python main.py --text "..."     # post this exact text instead of picking randomly
```

## Telegram-Triggered Posting
Sending a message to the configured Telegram bot posts that exact text as a reel, bypassing the random picker entirely (the content pools are untouched).

- Message format: plain text → posted under the default (first) category. Prefix with `category: ` to target a specific one, e.g. `annoyed: kal se diet start karungi`.
- `.github/workflows/telegram-post.yml` polls Telegram's `getUpdates` API every 5 minutes. If there's no new message, it does nothing — this is separate from and doesn't affect the regular scheduled posting in `post.yml`.
- `telegram_listener.py` tracks the last processed message in `telegram_offset.json` so nothing is ever posted twice.
- Setup: create a bot via [@BotFather](https://t.me/BotFather) to get `TELEGRAM_BOT_TOKEN`. Message the bot once, then call `https://api.telegram.org/bot<token>/getUpdates` in a browser to read your `chat.id` for `TELEGRAM_CHAT_ID`. Add both as GitHub Actions repo secrets.

## Environment Variables (.env)

```
GROQ_API_KEY=...
IG_USER_ID=...
IG_ACCESS_TOKEN=...
IG_APP_SECRET=...
INSTAGRAM_USERNAME=...
POST_INTERVAL_HOURS=2
TELEGRAM_BOT_TOKEN=...   # optional — only needed for Telegram-triggered posting
TELEGRAM_CHAT_ID=...     # optional — only needed for Telegram-triggered posting
```

## Adding New Content
Append new lines (one one-liner per line, no numbering) to `content/annoyed_one_liners.txt`. To retire an already-posted line early, move it manually into `content/annoyed_one_liners_used.txt`.

## Adding a New Category
1. Add `content/{category}_one_liners.txt` with one-liners, one per line
2. Add `content/{category}_one_liners_used.txt` (can start empty)
3. Add video backgrounds to `video/{category}/`
4. Add an entry to `CATEGORY_CONFIG` in `main.py`
5. Add a matching entry to `CATEGORY_LABELS` and `NICHE_TAG_BANKS` in `caption_generator.py`

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point — category selection, pipeline orchestration |
| `caption_generator.py` | Groq caption + hashtag generation |
| `image_composer.py` | English text rendered on transparent card (1080×1920); emoji drawn as color glyphs via pilmoji |
| `video_composer.py` | Card + video bg → MP4 reel with audio |
| `instagram_poster.py` | Instagram Graph API posting |
| `config.py` | API keys and settings |
| `telegram_listener.py` | Polls Telegram for a manual override message |
| `telegram_offset.json` | Tracks last processed Telegram message (avoids duplicate posts) |
| `audio/` | Background music (MP3/M4A/WAV) |
| `video/annoyed/` | Video backgrounds for the `annoyed` category |
| `content/annoyed_one_liners.txt` | Unused one-liners for the `annoyed` category |
| `content/annoyed_one_liners_used.txt` | Already-posted one-liners for the `annoyed` category |
