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
  #N (post number — added by main.py)
"""

import json
import re

from groq import Groq

from config import GROQ_API_KEY

_groq           = Groq(api_key=GROQ_API_KEY)
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"

CATEGORY_LABELS: dict[str, str] = {
    # Male
    "desi_household_and_relatives":  "Desi Household & Relatives",
    "creative_breakdown_and_editor": "Creative Breakdown & Editor",
    "group_chats_and_goa_plans":     "Group Chats & Goa Plans",
    "traffic_and_driving":           "Traffic & Driving",
    "dating_and_relationships":      "Dating & Relationships",
    "online_shopping_addiction":     "Online Shopping Addiction",
    "extreme_laziness_and_sleep":    "Extreme Laziness & Sleep",
    "gym_diet_and_delusions":        "Gym Diet & Delusions",
    # Female
    "girl_math_and_shopping":   "Girl Math & Shopping",
    "skincare_and_makeup":      "Skincare & Makeup",
    "besties_and_gossip":       "Besties & Gossip",
    "dating_and_delulu":        "Dating & Delulu",
    "mood_swings_and_pms":      "Mood Swings & Overthinking",
    "adulting_and_survival":    "Adulting & Everyday Survival",
}

# Curated niche tags per category (< 500K posts, high-signal for the algorithm).
# Groq picks 3 from the list that best match the specific one-liner.
NICHE_TAG_BANKS: dict[str, list[str]] = {
    "desi_household_and_relatives": [
        "#GharKaScene", "#DesiMoms", "#IndianParents", "#RishtedaarProblems",
        "#DesiFamily", "#GharWaliLife", "#IndianHousehold", "#TupperwareMom",
    ],
    "creative_breakdown_and_editor": [
        "#VideoEditorLife", "#DesignStruggle", "#CreativeBlock", "#EditorProblems",
        "#FreelancerLife", "#IndianCreatives", "#MotionDesigner", "#AfterEffectsLife",
    ],
    "group_chats_and_goa_plans": [
        "#GoaPlans", "#GroupChatDrama", "#DostiyaanWali", "#CancelledPlans",
        "#IndianFriendGroup", "#WhatsappGroup", "#YaariDostaana", "#BestieProblems",
    ],
    "traffic_and_driving": [
        "#IndianTraffic", "#OlaUberProblems", "#DrivingInIndia", "#RoadRageIndia",
        "#MetroLife", "#DelhiTraffic", "#MumbaiTraffic", "#HornOKPlease",
    ],
    "dating_and_relationships": [
        "#TalkingStage", "#DesiDating", "#IndianCrush", "#RelationshipDesi",
        "#BollywoodLove", "#SingleInIndia", "#DatingInIndia", "#RedFlagsDesi",
    ],
    "online_shopping_addiction": [
        "#MyntraAddict", "#AmazonIndia", "#OnlineShoppingIndia", "#SaleHaiTohKharido",
        "#CartAbandonment", "#FreeDelivery", "#ShoppingAddict", "#FlipkartSale",
    ],
    "extreme_laziness_and_sleep": [
        "#SnoozeButton", "#SonaHaiMujhe", "#NahanaNahiHai", "#BedLife",
        "#GharPeBaithe", "#ProcrastinationKing", "#AalsiLife", "#NeendMeraDharm",
    ],
    "gym_diet_and_delusions": [
        "#GymProblems", "#DietCheating", "#ProteinPowder", "#FitnessDelusion",
        "#LegDaySkipped", "#CheatDay", "#IndianGymLife", "#BicepsKahan",
    ],
    "girl_math_and_shopping": [
        "#GirlMath", "#MyntraSale", "#ShoppingLogic", "#WardrobeProblems",
        "#FashionStruggle", "#IndianShopaholic", "#SaleKaFanda", "#ZaraSale",
    ],
    "skincare_and_makeup": [
        "#SkincareIndia", "#EyelinerStruggle", "#IndianMakeup", "#GlassSkinGoal",
        "#MakeupLover", "#IndianSkincare", "#MeszyBun", "#LipBalm",
    ],
    "besties_and_gossip": [
        "#BestieGoals", "#GroupChatGossip", "#DesiGirlGang", "#BestfriendProblems",
        "#GossipSession", "#IndianBesties", "#WashoomTalk", "#GirlTalk",
    ],
    "dating_and_delulu": [
        "#DelululIsTheSolulu", "#RedFlagsIgnored", "#TalkingStageGirl",
        "#DesiGirlDating", "#ICanFixHim", "#BollywoodDelusion", "#GreenFlags",
    ],
    "mood_swings_and_pms": [
        "#PMSProblems", "#MoodSwingLife", "#OverthinkerClub", "#GirlMoods",
        "#EmotionalDesi", "#PeriodProblems", "#IndianGirlOverthinker", "#TherapyNeeded",
    ],
    "adulting_and_survival": [
        "#AdultingIsHard", "#GharKaKhana", "#IndependentWoman", "#BraOff",
        "#AdultingProblems", "#WFHLife", "#IndianAdulting", "#SpotifyPlaylist",
    ],
}

# Mid-size community tags (500K–10M) — shared across all posts
MID_TAGS_MALE   = ["#DesiHumor", "#IndianMillennials", "#RelatableContent",
                   "#HinglishMemes", "#BachpanKiYaadein", "#IndianMemesCommunity"]
MID_TAGS_FEMALE = ["#DesiGirls", "#IndianWomenHumor", "#RelatableGirl",
                   "#HinglishGirls", "#IndianGirlThings", "#DesiWomenMemes"]

# Broad reach tags (10M+) — paired to avoid overlap
BROAD_TAGS = ["#IndianMemes", "#Hinglish", "#DesiProblems",
              "#IndianComedy", "#DesiContent", "#IndianReels"]

FALLBACK: dict[str, str] = {
    "hook":           "Yaar yeh toh bilkul main hoon! 😂",
    "cta":            "Screenshot karo aur tag karo uss dost ko jo yeh hai.",
    "niche_hashtags": "#GharKaScene #DesiHumor #RelatableContent",
    "mid_hashtags":   "#IndianMillennials #HinglishMemes #BachpanKiYaadein",
    "broad_hashtags": "#IndianMemes #Hinglish #DesiProblems",
    "search_keyword": "relatable desi content",
    "alt_text":       "Relatable Hinglish comedy one-liner",
}


def _build_prompt(text: str, label: str, niche_bank: list[str], gender: str) -> str:
    mid_pool  = MID_TAGS_MALE if gender == "male" else MID_TAGS_FEMALE
    niche_str = " ".join(niche_bank)
    mid_str   = " ".join(mid_pool)
    broad_str = " ".join(BROAD_TAGS)

    return f"""You are an Instagram growth strategist for a viral Hinglish comedy page targeting Indian millennials.

ONE-LINER: {text}
CATEGORY: {label}
GENDER AUDIENCE: {gender}

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


def generate_caption_for_oneliner(
    text: str, category: str, number: int, gender: str = "male"
) -> dict:
    label      = CATEGORY_LABELS.get(category, category.replace("_", " ").title())
    niche_bank = NICHE_TAG_BANKS.get(category, ["#DesiHumor", "#RelatableContent", "#IndianMemes"])
    prompt     = _build_prompt(text, label, niche_bank, gender)

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

            print(f"  [groq] Caption OK for #{number}")
            return data

        except Exception as exc:
            print(f"  [groq] Attempt {attempt} failed: {type(exc).__name__}: {str(exc)[:80]}")

    print("  [groq] All attempts failed — using fallback")
    return {**FALLBACK, "alt_text": f"Relatable Hinglish comedy one-liner about {label}"}
