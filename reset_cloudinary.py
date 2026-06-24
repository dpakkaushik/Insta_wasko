"""Delete all template images from Cloudinary under insta_radha/ then re-upload from local templates/."""
import cloudinary
import cloudinary.api
import cloudinary.uploader

from config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
)

print("Fetching all images under insta_radha/...")
deleted = 0
next_cursor = None
while True:
    kwargs = {"type": "upload", "resource_type": "image", "prefix": "insta_radha/", "max_results": 500}
    if next_cursor:
        kwargs["next_cursor"] = next_cursor
    result = cloudinary.api.resources(**kwargs)
    resources = result.get("resources", [])
    for r in resources:
        pid = r["public_id"]
        cloudinary.uploader.destroy(pid, resource_type="image")
        print(f"  DELETED {pid}")
        deleted += 1
    next_cursor = result.get("next_cursor")
    if not next_cursor:
        break

print(f"\nDeleted {deleted} images. Now uploading from templates/...\n")
