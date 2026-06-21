import os
from dotenv import load_dotenv

load_dotenv(override=False)  # env vars from GitHub Actions take priority

def _clean(val: str) -> str:
    """Strip whitespace and take only the first line (guards against double-paste in GitHub Secrets)."""
    return val.strip().splitlines()[0].strip() if val.strip() else val

GEMINI_API_KEY      = _clean(os.getenv("GEMINI_API_KEY", ""))
GROQ_API_KEY        = _clean(os.getenv("GROQ_API_KEY", ""))
HF_API_TOKEN        = _clean(os.getenv("HF_API_TOKEN", ""))  # optional — huggingface.co free token
INSTAGRAM_USERNAME  = _clean(os.getenv("INSTAGRAM_USERNAME", ""))
QUOTE_CATEGORY      = os.getenv("QUOTE_CATEGORY", "mindset")
POST_INTERVAL_HOURS = int(os.getenv("POST_INTERVAL_HOURS", "1"))

# Official Instagram Graph API
IG_USER_ID      = _clean(os.getenv("IG_USER_ID", ""))
IG_ACCESS_TOKEN = _clean(os.getenv("IG_ACCESS_TOKEN", ""))
IG_APP_SECRET   = _clean(os.getenv("IG_APP_SECRET", ""))
IMGBB_API_KEY   = _clean(os.getenv("IMGBB_API_KEY", ""))

# Cloudinary — for video hosting (required for Reel posts)
CLOUDINARY_CLOUD_NAME = _clean(os.getenv("CLOUDINARY_CLOUD_NAME", ""))
CLOUDINARY_API_KEY    = _clean(os.getenv("CLOUDINARY_API_KEY", ""))
CLOUDINARY_API_SECRET = _clean(os.getenv("CLOUDINARY_API_SECRET", ""))

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set — get one at https://aistudio.google.com/apikey")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set — get a free key at https://console.groq.com/keys")
if not IG_USER_ID or not IG_ACCESS_TOKEN:
    raise ValueError("IG_USER_ID and IG_ACCESS_TOKEN must be set in .env / GitHub Secrets")
if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
    raise ValueError(
        "CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET must be set — "
        "get a free account at https://cloudinary.com"
    )
