"""
One-time (and incremental) script to upload template images from local
templates/ folder to Cloudinary, preserving the folder structure as
the Cloudinary public_id.

Usage:
  python upload_templates.py              # upload all missing images
  python upload_templates.py --force      # re-upload even if already exists

Cloudinary path mirrors local path:
  templates/overthinking_and_anxiety/boy/dark/img1.jpg
  → cloudinary public_id: insta_radha/overthinking_and_anxiety/boy/dark/img1
"""

import sys
from pathlib import Path

TEMPLATE_DIR    = Path("templates")
CLOUDINARY_ROOT = "insta_radha"


def _init_cloudinary():
    try:
        import cloudinary
        import cloudinary.uploader
        import cloudinary.api
    except ImportError:
        raise RuntimeError("Run: pip install cloudinary")

    from config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
    )
    return cloudinary


def _existing_public_ids(cloudinary) -> set[str]:
    """Fetch all public_ids already uploaded under insta_radha/."""
    ids: set[str] = set()
    next_cursor = None
    while True:
        kwargs = {"type": "upload", "prefix": CLOUDINARY_ROOT + "/", "max_results": 500}
        if next_cursor:
            kwargs["next_cursor"] = next_cursor
        result = cloudinary.api.resources(**kwargs)
        for r in result.get("resources", []):
            ids.add(r["public_id"])
        next_cursor = result.get("next_cursor")
        if not next_cursor:
            break
    return ids


def main():
    force = "--force" in sys.argv
    cloudinary = _init_cloudinary()
    import cloudinary.uploader

    images = (
        list(TEMPLATE_DIR.glob("**/*.jpg"))
        + list(TEMPLATE_DIR.glob("**/*.jpeg"))
        + list(TEMPLATE_DIR.glob("**/*.png"))
        + list(TEMPLATE_DIR.glob("**/*.webp"))
    )

    if not images:
        print("No images found in templates/ — add images first.")
        return

    print(f"Found {len(images)} image(s) in templates/")

    existing = set() if force else _existing_public_ids(cloudinary)
    print(f"Already on Cloudinary: {len(existing)}")

    uploaded = 0
    skipped  = 0

    for img_path in sorted(images):
        rel      = img_path.relative_to(TEMPLATE_DIR)
        public_id = f"{CLOUDINARY_ROOT}/{rel.with_suffix('')}".replace("\\", "/")

        if public_id in existing:
            print(f"  SKIP  {rel}")
            skipped += 1
            continue

        print(f"  UP    {rel} ...", end=" ", flush=True)
        try:
            cloudinary.uploader.upload(
                str(img_path),
                public_id=public_id,
                resource_type="image",
                overwrite=True,
            )
            print("OK")
            uploaded += 1
        except Exception as exc:
            print(f"FAIL ({exc})")

    print(f"\nDone. Uploaded: {uploaded}  Skipped: {skipped}")


if __name__ == "__main__":
    main()
