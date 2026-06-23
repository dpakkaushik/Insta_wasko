import json
import re
import time
from pathlib import Path

from google import genai
from groq import Groq

from config import GEMINI_API_KEY, GROQ_API_KEY

_gemini = genai.Client(api_key=GEMINI_API_KEY)
_groq   = Groq(api_key=GROQ_API_KEY)

GEMINI_TEXT_MODEL = "gemini-2.5-flash"
GROQ_TEXT_MODEL   = "llama-3.3-70b-versatile"
PROMPTS_DIR       = Path("prompts")


def _parse_quote_json(raw: str, source: str) -> dict:
    # Strip markdown code fences if present
    raw = re.sub(r"^```[a-z]*\n?", "", raw).strip()
    raw = re.sub(r"\n?```$", "", raw).strip()
    # Extract the JSON object even if the model prepended plain-text lines
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"[{source}] No JSON object found in response | Raw: {raw[:200]}")
    data = json.loads(match.group())
    required = {"category", "quote", "caption", "hashtags", "search_keyword", "alt_text"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"[{source}] Missing fields: {missing} | Raw: {raw[:200]}")
    if isinstance(data["hashtags"], list):
        data["hashtags"] = " ".join(data["hashtags"])
    return data


GEMINI_MIN_WORDS_EN = 20
GEMINI_MIN_WORDS_HI = 15   # Hindi words are denser; 15 HI ~ 20 EN in content
GROQ_MIN_WORDS      = 8    # Groq generates shorter but valid replies — don't over-filter
ME_MIN_WORDS        = 4    # "Me:" line must be a specific micro-moment, not a 1-3 word phrase


def _is_hindi(text: str) -> bool:
    return bool(re.search(r"[ऀ-ॿ]", text))


def _me_word_count(data: dict) -> tuple[int, int]:
    """Return (word_count, minimum) for the Me: line."""
    quote = data.get("quote", "")
    me_line = quote.split("\n", 1)[0]
    text = re.sub(r"^Me:\s*", "", me_line, flags=re.IGNORECASE)
    return len(text.split()), ME_MIN_WORDS


def _krishna_word_count(data: dict, source: str) -> tuple[int, int]:
    """Return (word_count, minimum) based on source and script."""
    quote = data.get("quote", "")
    lines = quote.split("\n", 1)
    krishna_line = lines[1] if len(lines) > 1 else ""
    text = re.sub(r"^Krishna:\s*", "", krishna_line, flags=re.IGNORECASE)
    if source == "groq":
        minimum = GROQ_MIN_WORDS
    elif _is_hindi(text):
        minimum = GEMINI_MIN_WORDS_HI
    else:
        minimum = GEMINI_MIN_WORDS_EN
    return len(text.split()), minimum


def _call_gemini(full_prompt: str) -> dict:
    response = _gemini.models.generate_content(
        model=GEMINI_TEXT_MODEL,
        contents=full_prompt,
    )
    return _parse_quote_json(response.text.strip(), "gemini")


def _call_groq(full_prompt: str) -> dict:
    # Split into system (persona + rules) and user (output instruction) for better compliance
    lines = full_prompt.strip().splitlines()
    split_marker = next(
        (i for i, l in enumerate(lines) if l.strip().startswith("Then output ONLY")),
        None,
    )
    if split_marker is not None:
        system_msg = "\n".join(lines[:split_marker]).strip()
        user_msg   = "\n".join(lines[split_marker:]).strip()
    else:
        system_msg = full_prompt
        user_msg   = "Generate the Krishna Q&A dialogue now."

    response = _groq.chat.completions.create(
        model=GROQ_TEXT_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.9,
        max_tokens=1024,
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise ValueError("[groq] Empty response returned")
    return _parse_quote_json(content, "groq")


def _load_prompt(category: str, gender: str, language: str, variant: str = "") -> str:
    suffix = f"_{variant}" if variant else ""
    path = PROMPTS_DIR / f"{category}{suffix}.txt"
    if not path.exists():
        path = PROMPTS_DIR / f"{category}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return (
        path.read_text(encoding="utf-8").strip()
        .replace("{selected_gender}", gender)
        .replace("{selected_language}", language)
    )


def generate_carousel(category: str, gender: str, language: str = "english") -> dict:
    """Generate Krishna Q&A dialogue for a given category and gender."""
    prompt = _load_prompt(category, gender, language)

    for attempt in range(1, 6):
        print(f"  [gemini] Calling {GEMINI_TEXT_MODEL} (attempt {attempt})...")
        try:
            data = _call_gemini(prompt)
            me_wc, me_min = _me_word_count(data)
            if me_wc < me_min:
                print(f"  [gemini] Me: too short ({me_wc}/{me_min} words) — retrying...")
                continue
            wc, minimum = _krishna_word_count(data, "gemini")
            if wc >= minimum:
                print(f"  [gemini] OK (Me:{me_wc}w Krishna:{wc}w)")
                return data
            print(f"  [gemini] Krishna too short ({wc}/{minimum} words) — retrying...")
        except Exception as exc:
            err = str(exc)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = 20 * attempt
                print(f"  [gemini] Rate limited — waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  [gemini] Error ({exc.__class__.__name__}: {err[:80]}) — retrying...")

    # Gemini exhausted — try Groq as fallback
    print("  [groq] Gemini exhausted — attempting Groq fallback...")
    try:
        groq_prompt = _load_prompt(category, gender, language, variant="groq")
        data = _call_groq(groq_prompt)
        wc, _ = _krishna_word_count(data, "groq")
        print(f"  [groq] Fallback OK ({wc}w)")
        return data
    except Exception as exc:
        raise RuntimeError(
            f"Quote generation failed: Gemini exhausted, Groq fallback also failed ({exc}). "
            "Check API keys or wait for rate limits to clear."
        )
