import json
import re
from pathlib import Path

from google import genai
from groq import Groq

from config import GEMINI_API_KEY, GROQ_API_KEY

_gemini = genai.Client(api_key=GEMINI_API_KEY)
_groq   = Groq(api_key=GROQ_API_KEY)

GEMINI_TEXT_MODEL = "gemini-2.5-flash"
GROQ_TEXT_MODEL   = "llama-3.3-70b-versatile"
QUOTE_PROMPT_FILE = Path("prompts/quote_prompt.txt")


def _parse_quote_json(raw: str, source: str) -> dict:
    raw = re.sub(r"^```[a-z]*\n?", "", raw).strip()
    raw = re.sub(r"\n?```$", "", raw).strip()
    data = json.loads(raw)
    required = {"mood_number", "mood_name", "quote", "caption", "hashtags", "search_keyword", "alt_text"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"[{source}] Missing fields: {missing} | Raw: {raw[:200]}")
    data["mood_number"] = int(data["mood_number"])
    return data


def generate_carousel(mood_number: int, template_description: str = "") -> dict:
    """Generate quote for a given mood. Tries Gemini 2.5 Flash first, falls back to Groq."""
    base_prompt = QUOTE_PROMPT_FILE.read_text().strip()
    full_prompt = (
        f"mood_number: {mood_number}\n"
        f"template_description: {template_description or 'not provided'}\n\n"
        f"{base_prompt}"
    )

    # Primary: Gemini 2.5 Flash
    print(f"  [gemini] Calling {GEMINI_TEXT_MODEL}...")
    try:
        response = _gemini.models.generate_content(
            model=GEMINI_TEXT_MODEL,
            contents=full_prompt,
        )
        data = _parse_quote_json(response.text.strip(), "gemini")
        print(f"  [gemini] Quote OK")
        return data
    except Exception as exc:
        print(f"  [gemini] Failed ({exc.__class__.__name__}: {str(exc)[:120]}) → falling back to Groq...")

    # Fallback: Groq
    print(f"  [groq] Calling {GROQ_TEXT_MODEL}...")
    try:
        response = _groq.chat.completions.create(
            model=GROQ_TEXT_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.9,
            max_tokens=1024,
        )
        data = _parse_quote_json(response.choices[0].message.content.strip(), "groq")
        print(f"  [groq] Quote OK")
        return data
    except Exception as exc:
        raise RuntimeError(
            f"[groq] Quote generation also failed: {exc}\n"
            "Check GROQ_API_KEY and GEMINI_API_KEY."
        ) from exc
