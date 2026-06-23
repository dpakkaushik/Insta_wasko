import os
from dotenv import load_dotenv

load_dotenv(override=False)  # env vars from GitHub Actions take priority


def _clean(val: str) -> str:
    return val.strip().splitlines()[0].strip() if val.strip() else val


GEMINI_API_KEY      = _clean(os.getenv("GEMINI_API_KEY", ""))
GROQ_API_KEY        = _clean(os.getenv("GROQ_API_KEY", ""))
INSTAGRAM_USERNAME  = _clean(os.getenv("INSTAGRAM_USERNAME", ""))
POST_INTERVAL_HOURS = int(os.getenv("POST_INTERVAL_HOURS", "2"))

IG_USER_ID      = _clean(os.getenv("IG_USER_ID", ""))
IG_ACCESS_TOKEN = _clean(os.getenv("IG_ACCESS_TOKEN", ""))
IG_APP_SECRET   = _clean(os.getenv("IG_APP_SECRET", ""))

CLOUDINARY_CLOUD_NAME = _clean(os.getenv("CLOUDINARY_CLOUD_NAME", ""))
CLOUDINARY_API_KEY    = _clean(os.getenv("CLOUDINARY_API_KEY", ""))
CLOUDINARY_API_SECRET = _clean(os.getenv("CLOUDINARY_API_SECRET", ""))

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set")
if not IG_USER_ID or not IG_ACCESS_TOKEN:
    raise ValueError("IG_USER_ID and IG_ACCESS_TOKEN must be set")
if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
    raise ValueError("CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET must be set")
