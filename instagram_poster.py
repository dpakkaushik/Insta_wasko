"""
Instagram poster — Official Instagram Content Publishing API.
Posts Reels via Cloudinary (video host) + Instagram Graph API.

Token management:
  - Token from .env is stored with a 60-day estimate on first run
  - Auto-refreshed when < 7 days remain
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from config import (
    IG_USER_ID, IG_ACCESS_TOKEN, IG_APP_SECRET,
    INSTAGRAM_USERNAME,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET,
)

GRAPH      = "https://graph.instagram.com/v21.0"
TOKEN_FILE = Path("ig_token.json")


def _exchange_token(short_token: str) -> dict:
    r = requests.get(
        "https://graph.instagram.com/access_token",
        params={
            "grant_type":    "ig_exchange_token",
            "client_secret": IG_APP_SECRET,
            "access_token":  short_token,
        },
        timeout=15,
    )
    if not r.ok:
        raise RuntimeError(
            f"[token] Exchange failed ({r.status_code}): {r.json()}\n"
            "Generate a fresh token on the Meta Developer portal and update IG_ACCESS_TOKEN."
        )
    data = r.json()
    expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
    return {"access_token": data["access_token"], "expires_at": expires_at.isoformat()}


def _refresh_token(token: str) -> dict:
    r = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
    return {"access_token": data["access_token"], "expires_at": expires_at.isoformat()}


def _get_token() -> str:
    if TOKEN_FILE.exists():
        stored     = json.loads(TOKEN_FILE.read_text())
        token      = stored["access_token"]
        expires_at = datetime.fromisoformat(stored["expires_at"])
        days_left  = (expires_at - datetime.now()).days

        if days_left > 7:
            return token
        if days_left >= 0:
            print(f"[token] Expires in {days_left}d — refreshing...")
            try:
                stored = _refresh_token(token)
                TOKEN_FILE.write_text(json.dumps(stored, indent=2))
                return stored["access_token"]
            except Exception as exc:
                print(f"[token] Refresh failed ({exc}) — using existing token")
                return token
        print("[token] Token may be expired — update IG_ACCESS_TOKEN in .env and re-run")

    print("[token] Saving token from .env (valid ~60 days)...")
    stored = {
        "access_token": IG_ACCESS_TOKEN,
        "expires_at":   (datetime.now() + timedelta(days=60)).isoformat(),
    }
    TOKEN_FILE.write_text(json.dumps(stored, indent=2))
    return IG_ACCESS_TOKEN


def _host_video(video_path: str) -> tuple[str, str]:
    """Upload video to Cloudinary. Returns (secure_url, public_id)."""
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError as exc:
        raise RuntimeError(
            "[cloudinary] Package not installed. Run: pip install cloudinary\n"
            f"Original error: {exc}"
        ) from exc

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
    )

    file_size = Path(video_path).stat().st_size
    print(f"  [cloudinary] Uploading {Path(video_path).name} ({file_size/1024/1024:.1f} MB)...")
    try:
        result = cloudinary.uploader.upload(
            video_path,
            resource_type="video",
            folder="insta_radha/reels",
        )
    except Exception as exc:
        raise RuntimeError(
            f"[cloudinary] Upload failed: {type(exc).__name__}: {exc}\n"
            "Check CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET."
        ) from exc

    url = result["secure_url"]
    public_id = result["public_id"]
    print(f"  [cloudinary] URL: {url[:70]}...")
    return url, public_id




def _create_reel_container(token: str, video_url: str, caption: str, audio_name: str | None) -> str:
    params: dict = {
        "media_type":   "REELS",
        "video_url":    video_url,
        "caption":      caption[:2200],
        "access_token": token,
    }
    if audio_name:
        params["audio_name"] = audio_name

    r = requests.post(f"{GRAPH}/{IG_USER_ID}/media", params=params, timeout=30)
    if not r.ok:
        raise RuntimeError(
            f"[instagram] Create Reel container failed ({r.status_code}): {r.json()}"
        )
    return r.json()["id"]


def post_reel(video_path: str, caption: str, audio_name: str | None = None) -> str:
    token              = _get_token()
    video_url, _ = _host_video(video_path)

    container_id: str | None = None
    for audio in ([audio_name] if audio_name else []) + [None]:
        label = f'"{audio}"' if audio else "no audio"
        print(f"  [instagram] Creating Reel container — audio: {label}...")
        try:
            container_id = _create_reel_container(token, video_url, caption, audio)
            print(f"  [instagram] Container: {container_id}")
            break
        except RuntimeError as exc:
            if "audio" in str(exc).lower() and audio is not None:
                print(f"  [instagram] Audio {label} not accepted — trying without...")
                continue
            raise

    if container_id is None:
        raise RuntimeError("[instagram] Could not create Reel container")

    for attempt in range(30):
        time.sleep(10)
        status_data = requests.get(
            f"{GRAPH}/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=10,
        ).json()
        status = status_data.get("status_code", "IN_PROGRESS")
        print(f"  [instagram] Status: {status} (attempt {attempt + 1}/30)")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(
                f"[instagram] Reel processing failed: {status_data}\n"
                "Check video format: MP4, H.264, 3-90s, 9:16 aspect ratio."
            )
    else:
        raise RuntimeError(
            "[instagram] Reel processing timed out after 300s — check Instagram manually."
        )

    r = requests.post(
        f"{GRAPH}/{IG_USER_ID}/media_publish",
        params={"creation_id": container_id, "access_token": token},
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(
            f"[instagram] Publish failed ({r.status_code}): {r.json()}"
        )

    url = f"https://www.instagram.com/{INSTAGRAM_USERNAME}/"
    print(f"[instagram] Reel live -> {url}")
    return url
