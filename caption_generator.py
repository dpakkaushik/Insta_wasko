"""
Groq-powered caption and hashtag generator for Waskodigama comedy reels.

Hashtag strategy — 3-tier system per post:
  Niche  (3): < 500K posts — content classification signal
  Mid    (3): 500K–10M    — community discovery
  Broad  (3): 10M+        — reach amplification

Caption structure:
  Hook (<125 chars, visible before Instagram "...more")
  CTA  (save/tag nudge)
  9 hashtags
"""

import json
import re

from groq import Groq

from config import GROQ_API_KEY

_groq           = Groq(api_key=GROQ_API_KEY)
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"

CATEGORY_LABELS: dict[str, str] = {
    "annoyed": "Annoyed & Overthinking Girl Problems",
    "swag":    "Confident Swag Girl Vibes",
    "savage":  "Savage & Unbothered Girl Energy",
}

# Curated niche tags per category (< 500K posts, high-signal for the algorithm).
# Groq picks 3 from the list that best match the specific one-liner.
NICHE_TAG_BANKS: dict[str, list[str]] = {
    "annoyed": [
        "#AnnoyedAF", "#GirlMath", "#OverthinkerClub", "#BestieProblems",
        "#DelululIsTheSolulu", "#SkincareIndia", "#AdultingIsHard", "#MoodSwingLife",
    ],
    "swag": [
        "#SwagGirl", "#MainCharacterEnergy", "#BossBabeIndia", "#ConfidentGirl",
        "#GlowUpSeason", "#DesiSwag", "#IndependentGirl", "#ThatGirlVibes",
    ],
    "savage": [
        "#SavageGirl", "#UnbotheredQueen", "#NoChill", "#SelfRespectFirst",
        "#BoundaryQueen", "#ChaosGirl", "#ToxicFreeLife", "#NoFilterZone",
    ],
}

# Mid-size community tags (500K–10M) — shared across all posts, all
# girl/women-themed to match the content. Groq picks 3 per post; a bigger
# pool means fewer identical hashtag sets across consecutive posts
# (repetition is a known reach-killer on Instagram).
MID_TAGS = ["#DesiGirls", "#IndianWomenHumor", "#RelatableGirl",
            "#HinglishGirls", "#IndianGirlThings", "#DesiWomenMemes",
            "#IndianGirlProblems", "#DesiGirlMemes", "#GirlHumor",
            "#DesiGirlVibes", "#GirlsWhoRelate", "#IndianGirlGang",
            "#RelatableGirlMemes", "#IndianGirlSquad"]

# Broad reach tags (10M+) — all girl/women-themed. Includes some of the
# highest-volume girl-specific tags on Instagram (#GirlsOfInstagram,
# #GirlPower, #GirlBoss) for maximum reach without drifting off-niche into
# generic tags unrelated to the content (e.g. plain #Reels or #Viral).
BROAD_TAGS = ["#GirlsOfInstagram", "#IndianGirl", "#DesiGirl",
              "#GirlPower", "#InstaGirls", "#IndianWomen",
              "#GirlGang", "#GirlBoss", "#WomenOfIndia",
              "#DesiWomen", "#QueenVibes", "#GirlSquad",
              "#PakistaniGirl", "#PakistaniWomen",
              "#SouthAsianGirl", "#DesiGirlsUnite"]

FALLBACK: dict[str, str] = {
    "hook":           "Yaar yeh toh bilkul main hoon! 😂",
    "cta":            "Screenshot karo aur tag karo uss dost ko jo yeh hai.",
    "niche_hashtags": "#AnnoyedAF #GirlMath #OverthinkerClub",
    "mid_hashtags":   "#DesiGirls #HinglishGirls #IndianGirlThings",
    "broad_hashtags": "#IndianMemes #Hinglish #DesiProblems",
    "search_keyword": "relatable desi content",
    "alt_text":       "Relatable Hinglish comedy one-liner",
}


def _build_prompt(text: str, label: str, niche_bank: list[str]) -> str:
    niche_str = " ".join(niche_bank)
    mid_str   = " ".join(MID_TAGS)
    broad_str = " ".join(BROAD_TAGS)

    return f"""You are an Instagram growth strategist for a viral Hinglish comedy page targeting Indian and Pakistani women and girls (Hindi-Urdu-English mixed captions land well with both audiences).

ONE-LINER: {text}
CATEGORY: {label}

Write a caption and 3-tier hashtag set to maximize Reel reach.

CAPTION — TWO PARTS:

HOOK (key): Must be the FIRST thing. Under 110 characters. Visible before Instagram cuts to "...more".
  - React to / extend the joke in Hinglish
  - Punchy, specific, funny — NOT generic like "so relatable" or "this is me"
  - No hashtags here

CTA (save-driver): One line. Gets people to save or tag.
  - Use: "Screenshot karo", "Save karo jab yeh moment aaye", "Tag kar uss [specific person] ko"
  - Be specific to the joke topic — NOT generic "tag your friends"

HASHTAGS — pick from the pools below, exactly 3 from each tier:

NICHE pool (pick 3): {niche_str}
MID pool (pick 3): {mid_str}
BROAD pool (pick 3): {broad_str}

Output ONLY valid JSON, no markdown:
{{
  "hook": "...",
  "cta": "...",
  "niche_hashtags": "#tag1 #tag2 #tag3",
  "mid_hashtags": "#tag1 #tag2 #tag3",
  "broad_hashtags": "#tag1 #tag2 #tag3",
  "search_keyword": "2-4 word phrase for Instagram search",
  "alt_text": "one literal sentence describing the visual"
}}"""


def generate_caption_for_oneliner(text: str, category: str = "annoyed") -> dict:
    label      = CATEGORY_LABELS.get(category, category.replace("_", " ").title())
    niche_bank = NICHE_TAG_BANKS.get(category, ["#DesiGirls", "#RelatableContent", "#IndianMemes"])
    prompt     = _build_prompt(text, label, niche_bank)

    for attempt in range(1, 4):
        print(f"  [groq] Caption attempt {attempt}...")
        try:
            response = _groq.chat.completions.create(
                model=GROQ_TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.85,
                max_tokens=600,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("Empty response")

            raw   = re.sub(r"^```[a-z]*\n?", "", content).strip()
            raw   = re.sub(r"\n?```$", "", raw).strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise ValueError(f"No JSON found: {raw[:120]}")

            data = json.loads(match.group())
            if not all(k in data for k in ("hook", "cta", "niche_hashtags")):
                raise ValueError(f"Missing fields: {list(data.keys())}")

            print(f"  [groq] Caption OK")
            return data

        except Exception as exc:
            print(f"  [groq] Attempt {attempt} failed: {type(exc).__name__}: {str(exc)[:80]}")

    print("  [groq] All attempts failed — using fallback")
    return {**FALLBACK, "alt_text": f"Relatable Hinglish comedy one-liner about {label}"}
