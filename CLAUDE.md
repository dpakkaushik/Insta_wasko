# Waskodigama — Instagram Comedy Reel Pipeline

## What This Does
Posts Hinglish comedy one-liners as Instagram Reels, automatically, on a schedule.
Gender is picked randomly each run (male / female), with separate content banks and video backgrounds.

## Architecture

```
random gender → one-liner file → Groq (caption) → card → video bg overlay → Instagram
```

1. `main.py` picks gender randomly (male / female)
2. Reads the next one-liner sequentially from `video/{gender}/one-liners.md`
3. Groq generates a short Hinglish caption + hashtags
4. The one-liner text is rendered on a gradient background card (1080×1920 JPEG)
5. Card is composited over a video background from `video/{gender}/` (if any MP4s exist)
6. Final MP4 reel is posted to Instagram with caption + `#N` number at the end

## Content Banks

### Male (`video/male/one-liners.md`) — 80 one-liners
| # | Category |
|---|---------|
| 1–10 | Desi Household & Relatives |
| 11–20 | Creative Breakdown & Editor |
| 21–30 | Group Chats & Goa Plans |
| 31–40 | Traffic & Driving |
| 41–50 | Dating & Relationships |
| 51–60 | Online Shopping Addiction |
| 61–70 | Extreme Laziness & Sleep |
| 71–80 | Gym, Diet & Delusions |

### Female (`video/female/one-liners.md`) — 50 one-liners
| # | Category |
|---|---------|
| 1–9 | Girl Math & Shopping Delusions |
| 10–18 | Skincare, Makeup & The Messy Bun |
| 19–26 | Besties, Group Chats & Gossip |
| 27–35 | Dating, Delulu & I Can Fix Him |
| 36–44 | Mood Swings, PMS & Overthinking |
| 45–50 | Adulting & Everyday Survival |

## Sequential Tracking
- `oneliner_index_male.json` → `{"last_used": N}` for male content
- `oneliner_index_female.json` → `{"last_used": N}` for female content
- Each gender's index advances independently
- Caption ends with `#N` — when you see the last number (#80 male / #50 female), add new content

## Video Backgrounds
Drop MP4/MOV files into `video/male/` or `video/female/`.
- Pipeline picks a random video from the selected gender's folder each run
- Videos are looped or trimmed to fill the 30-second reel duration
- Resized/cropped to 9:16 (1080×1920) automatically
- Text card is overlaid at 80% opacity so background shows through
- If no video files exist, falls back to pure gradient background

## Audio
Drop MP3/M4A/WAV files into `audio/`. Picked randomly (no repeat for 3 runs).

## Running

```bash
python main.py          # run now, then every N hours (set POST_INTERVAL_HOURS in .env)
python main.py --once   # run exactly once
python main.py --dry    # generate card + reel, skip posting (for testing)
```

## Environment Variables (.env)

```
GROQ_API_KEY=...
IG_USER_ID=...
IG_ACCESS_TOKEN=...
IG_APP_SECRET=...
INSTAGRAM_USERNAME=...
POST_INTERVAL_HOURS=2
```

## Adding New Content
When a list is exhausted (caption shows `#80` for male, `#50` for female):
1. Append new numbered lines to `video/{gender}/one-liners.md` (continue numbering)
2. OR reset `oneliner_index_{gender}.json` to `{"last_used": 0}` to loop from #1

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point — gender selection, pipeline orchestration |
| `gemini_processor.py` | Groq caption + hashtag generation |
| `image_composer.py` | Text rendered on gradient card (1080×1920) |
| `video_composer.py` | Card + video bg → MP4 reel with audio |
| `instagram_poster.py` | Instagram Graph API posting |
| `config.py` | API keys and settings |
| `audio/` | Background music (MP3/M4A/WAV) |
| `video/male/` | Male one-liners + male video backgrounds |
| `video/female/` | Female one-liners + female video backgrounds |
| `oneliner_index_male.json` | Tracks last posted male one-liner |
| `oneliner_index_female.json` | Tracks last posted female one-liner |
