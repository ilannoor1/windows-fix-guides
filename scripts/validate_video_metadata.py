import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
VIDEOS_DIR = ROOT / "data" / "videos"

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def fail(message):
    print(f"ERROR: {message}")
    return False


def valid_http_url(value):
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def validate_file(path):
    print(f"\nChecking: {path.relative_to(ROOT)}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return fail(
            f"{path.name}: invalid JSON "
            f"(line {exc.lineno}, column {exc.colno})"
        )
    except OSError as exc:
        return fail(f"{path.name}: cannot read file: {exc}")

    if not isinstance(data, dict):
        return fail(f"{path.name}: top-level JSON must be an object.")

    required_fields = [
        "enabled",
        "video_id",
        "title",
        "slug",
        "description",
        "publication_date",
        "duration_seconds",
        "category",
        "thumbnail_url",
        "youtube_url",
        "related_guides",
        "commands",
    ]

    missing = [field for field in required_fields if field not in data]

    if missing:
        return fail(
            f"{path.name}: missing required fields: {', '.join(missing)}"
        )

    if not isinstance(data["enabled"], bool):
        return fail(f"{path.name}: 'enabled' must be true or false.")

    # Disabled files may be templates/drafts.
    # They must have the correct structure but are not publishable.
    if data["enabled"] is False:
        if not isinstance(data["related_guides"], list):
            return fail(f"{path.name}: 'related_guides' must be a list.")

        if not isinstance(data["commands"], list):
            return fail(f"{path.name}: 'commands' must be a list.")

        print("STATUS: DISABLED")
        print("No production publishing will be allowed from this file.")
        return True

    # Everything below is mandatory for ENABLED production entries.

    video_id = data["video_id"]

    if not isinstance(video_id, str) or not YOUTUBE_ID_RE.fullmatch(video_id):
        return fail(
            f"{path.name}: enabled video must have a valid "
            "11-character YouTube video ID."
        )

    title = data["title"]

    if not isinstance(title, str) or not title.strip():
        return fail(f"{path.name}: 'title' cannot be empty.")

    if len(title.strip()) > 200:
        return fail(f"{path.name}: 'title' is unexpectedly long.")

    slug = data["slug"]

    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        return fail(
            f"{path.name}: 'slug' must use lowercase letters, "
            "numbers and hyphens only."
        )

    if ".." in slug or "/" in slug or "\\" in slug:
        return fail(f"{path.name}: unsafe slug detected.")

    description = data["description"]

    if not isinstance(description, str) or len(description.strip()) < 20:
        return fail(
            f"{path.name}: description must contain at least "
            "20 characters."
        )

    publication_date = data["publication_date"]

    if not isinstance(publication_date, str):
        return fail(f"{path.name}: 'publication_date' must be text.")

    try:
        parsed_date = datetime.fromisoformat(
            publication_date.replace("Z", "+00:00")
        )
    except ValueError:
        return fail(
            f"{path.name}: publication_date must be valid ISO 8601."
        )

    if parsed_date.tzinfo is None:
        return fail(
            f"{path.name}: publication_date must include a timezone."
        )

    duration = data["duration_seconds"]

    if (
        not isinstance(duration, int)
        or isinstance(duration, bool)
        or duration <= 0
    ):
        return fail(
            f"{path.name}: duration_seconds must be a positive integer."
        )

    category = data["category"]

    if not isinstance(category, str) or not category.strip():
        return fail(f"{path.name}: 'category' cannot be empty.")

    thumbnail_url = data["thumbnail_url"]

    if not isinstance(thumbnail_url, str) or not valid_http_url(thumbnail_url):
        return fail(f"{path.name}: invalid thumbnail_url.")

    youtube_url = data["youtube_url"]

    if not isinstance(youtube_url, str) or not valid_http_url(youtube_url):
        return fail(f"{path.name}: invalid youtube_url.")

    allowed_youtube_hosts = {
        "youtube.com",
        "www.youtube.com",
        "youtu.be",
        "m.youtube.com",
    }

    youtube_host = urlparse(youtube_url).netloc.lower()

    if youtube_host not in allowed_youtube_hosts:
        return fail(
            f"{path.name}: youtube_url must point to YouTube."
        )

    if video_id not in youtube_url:
        return fail(
            f"{path.name}: youtube_url does not contain the declared video_id."
        )

    if video_id not in thumbnail_url:
        return fail(
            f"{path.name}: thumbnail_url does not contain the declared video_id."
        )

    related_guides = data["related_guides"]

    if not isinstance(related_guides, list):
        return fail(f"{path.name}: 'related_guides' must be a list.")

    for guide in related_guides:
        if not isinstance(guide, str):
            return fail(
                f"{path.name}: every related guide must be text."
            )

        if not guide.startswith("/") or not guide.endswith("/"):
            return fail(
                f"{path.name}: related guide '{guide}' must start "
                "and end with '/'."
            )

        if ".." in guide or "\\" in guide:
            return fail(
                f"{path.name}: unsafe related guide path: {guide}"
            )

    commands = data["commands"]

    if not isinstance(commands, list):
        return fail(f"{path.name}: 'commands' must be a list.")

    print("STATUS: ENABLED AND VALID")
    return True


def main():
    if not VIDEOS_DIR.exists():
        print(f"ERROR: Video metadata folder not found: {VIDEOS_DIR}")
        return 1

    files = sorted(VIDEOS_DIR.glob("*.json"))

    if not files:
        print("ERROR: No video metadata JSON files found.")
        return 1

    print("UniTech LK Video Metadata Validator")
    print("-----------------------------------")
    print(f"Found {len(files)} metadata file(s).")

    all_valid = True

    for path in files:
        if not validate_file(path):
            all_valid = False

    print("\n-----------------------------------")

    if all_valid:
        print("SUCCESS: All video metadata files passed validation.")
        return 0

    print("FAILED: One or more metadata files contain errors.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
