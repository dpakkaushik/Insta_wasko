"""
Weekly cleanup — deletes all videos in insta_radha/reels/ from Cloudinary.

Run manually:  python cleanup_cloudinary.py
GitHub Actions: scheduled weekly via .github/workflows/cleanup.yml
"""

import cloudinary
import cloudinary.api
import cloudinary.uploader

from config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
)

REELS_FOLDER = "insta_radha/reels"


def cleanup():
    print(f"Fetching videos in {REELS_FOLDER}...")
    deleted = 0
    failed  = 0
    next_cursor = None

    while True:
        kwargs = {
            "type":         "upload",
            "resource_type": "video",
            "prefix":       REELS_FOLDER + "/",
            "max_results":  100,
        }
        if next_cursor:
            kwargs["next_cursor"] = next_cursor

        result = cloudinary.api.resources(**kwargs)
        resources = result.get("resources", [])

        if not resources:
            break

        for r in resources:
            pid = r["public_id"]
            try:
                cloudinary.uploader.destroy(pid, resource_type="video")
                print(f"  DELETED  {pid}")
                deleted += 1
            except Exception as exc:
                print(f"  FAILED   {pid}: {exc}")
                failed += 1

        next_cursor = result.get("next_cursor")
        if not next_cursor:
            break

    print(f"\nDone. Deleted: {deleted}  Failed: {failed}")


if __name__ == "__main__":
    cleanup()
