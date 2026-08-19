import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEOS_DIR = ROOT / "data" / "videos"

SITE_URL = "https://unitechlk.com"

SITEMAP = ROOT / "sitemap.xml"
VIDEO_SITEMAP = ROOT / "video-sitemap.xml"

CATEGORY_HUBS = {
    "powershell": "/powershell/",
    "windows": "/windows/",
    "windows-storage": "/windows-storage/",
    "windows-security": "/windows-security/",
    "microsoft-office": "/microsoft-office/",
    "printers": "/printers/",
    "cmd": "/cmd/",
    "mobile": "/mobile/",
}


def seconds_to_iso8601(seconds):
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    result = "PT"

    if hours:
        result += f"{hours}H"

    if minutes:
        result += f"{minutes}M"

    if secs or result == "PT":
        result += f"{secs}S"

    return result


def local_path_from_url_path(url_path):
    clean = url_path.strip("/")

    if not clean:
        return ROOT

    return ROOT / clean


def load_metadata(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_text_if_exists(path):
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8")


def inspect_related_guides(data):
    problems = []

    for guide in data.get("related_guides", []):
        target = local_path_from_url_path(guide)

        if not target.exists():
            problems.append(
                f"Related guide does not exist in repository: {guide}"
            )

    return problems


def inspect_existing_production(slug, video_id):
    canonical = f"{SITE_URL}/{slug}/"
    output_file = ROOT / slug / "index.html"

    sitemap_text = read_text_if_exists(SITEMAP)
    video_sitemap_text = read_text_if_exists(VIDEO_SITEMAP)

    return {
        "page_exists": output_file.exists(),
        "in_sitemap": canonical in sitemap_text,
        "video_in_video_sitemap": video_id in video_sitemap_text,
        "canonical": canonical,
        "output_file": output_file,
    }


def show_existing_status(existing):
    print()
    print("PRODUCTION CHECK")
    print("----------------")

    print(
        f"Page exists:         "
        f"{'YES' if existing['page_exists'] else 'NO'}"
    )

    print(
        f"In sitemap.xml:      "
        f"{'YES' if existing['in_sitemap'] else 'NO'}"
    )

    print(
        f"In video sitemap:    "
        f"{'YES' if existing['video_in_video_sitemap'] else 'NO'}"
    )


def has_existing_production(existing):
    return any(
        [
            existing["page_exists"],
            existing["in_sitemap"],
            existing["video_in_video_sitemap"],
        ]
    )


def plan_video(path):
    print()
    print("=" * 70)
    print(f"Metadata: {path.relative_to(ROOT)}")
    print("=" * 70)

    try:
        data = load_metadata(path)
    except Exception as exc:
        print(f"BLOCKED: Unable to read metadata: {exc}")
        return False

    enabled = data.get("enabled") is True
    video_id = data.get("video_id", "")
    slug = data.get("slug", "")

    existing = inspect_existing_production(slug, video_id)

    print(f"Enabled:        {'YES' if enabled else 'NO'}")
    print(f"Video ID:       {video_id}")
    print(f"Slug:           {slug}")
    print(f"Canonical URL:  {existing['canonical']}")

    show_existing_status(existing)

    existing_production = has_existing_production(existing)

    # ---------------------------------------------------------
    # DISABLED METADATA
    # ---------------------------------------------------------

    if not enabled:
        print()
        print("STATUS: DISABLED")

        if existing_production:
            print("CLASSIFICATION: EXISTING PRODUCTION CONTENT")
            print("PROTECTION: LOCKED")
            print()
            print("ACTION: SKIP")
            print(
                "This metadata describes content already present "
                "in production."
            )
            print("No overwrite or duplicate generation is allowed.")
        else:
            print("CLASSIFICATION: NEW / UNPUBLISHED METADATA")
            print()
            print("ACTION: SKIP")
            print(
                "Metadata is disabled, so no future publishing "
                "action is permitted."
            )

        print()
        print("NO FILES WERE CHANGED.")
        return True

    # ---------------------------------------------------------
    # ENABLED METADATA
    # ---------------------------------------------------------

    print()
    print("STATUS: ENABLED")

    category = data.get("category", "")
    hub = CATEGORY_HUBS.get(category)

    if hub is None:
        print()
        print(f"BLOCKED: Unknown category '{category}'")
        print("Allowed categories:")

        for allowed in sorted(CATEGORY_HUBS):
            print(f"  - {allowed}")

        print()
        print("NO FILES WERE CHANGED.")
        return False

    title = data["title"]
    duration_seconds = data["duration_seconds"]
    duration_iso = seconds_to_iso8601(duration_seconds)

    print()
    print("DRY-RUN PLAN")
    print("------------")
    print(f"Title:          {title}")
    print(f"Category:       {category}")
    print(f"Category hub:   {hub}")
    print(
        f"Output file:    "
        f"{existing['output_file'].relative_to(ROOT)}"
    )
    print(
        f"Embed URL:      "
        f"https://www.youtube.com/embed/{video_id}"
    )
    print(f"Duration:       {duration_iso}")

    # Existing production content must never be overwritten
    # by the automatic new-guide generator.

    if existing_production:
        print()
        print("SAFETY CHECK: BLOCKED")
        print("---------------------")
        print(
            "Existing production content was detected for this "
            "video or slug."
        )

        if existing["page_exists"]:
            print("- Existing index.html detected.")

        if existing["in_sitemap"]:
            print("- Canonical URL already exists in sitemap.xml.")

        if existing["video_in_video_sitemap"]:
            print("- Video ID already exists in video-sitemap.xml.")

        print()
        print("AUTOMATIC OVERWRITE IS FORBIDDEN.")
        print("NO FILES WERE CHANGED.")
        return False

    problems = []

    hub_path = local_path_from_url_path(hub)

    if not hub_path.exists():
        problems.append(
            f"Category hub does not exist in repository: {hub}"
        )

    problems.extend(inspect_related_guides(data))

    if problems:
        print()
        print("SAFETY CHECK: BLOCKED")
        print("---------------------")

        for problem in problems:
            print(f"- {problem}")

        print()
        print("NO FILES WERE CHANGED.")
        return False

    print()
    print("SAFETY CHECK: PASS")
    print("------------------")
    print("CLASSIFICATION: NEW VIDEO GUIDE")
    print("STATUS: ELIGIBLE FOR FUTURE GENERATION")
    print()

    print("A future publisher would:")
    print(f"1. Create: {slug}/index.html")
    print(f"2. Add page to category hub: {hub}")
    print("3. Add canonical URL to sitemap.xml")
    print("4. Add video entry to video-sitemap.xml")
    print("5. Validate generated HTML and XML")
    print("6. Commit only after every check passes")
    print()
    print("DRY RUN ONLY — NOTHING WAS WRITTEN.")

    return True


def main():
    print("UniTech LK Video Guide Planner")
    print("==============================")
    print("MODE: DRY RUN ONLY")
    print("This script does not create, edit or delete website files.")

    if not VIDEOS_DIR.exists():
        print(f"ERROR: Missing metadata directory: {VIDEOS_DIR}")
        return 1

    files = sorted(VIDEOS_DIR.glob("*.json"))

    if not files:
        print("ERROR: No video metadata files found.")
        return 1

    all_ok = True

    for path in files:
        if not plan_video(path):
            all_ok = False

    print()
    print("=" * 70)

    if all_ok:
        print("DRY RUN COMPLETE: No production files were changed.")
        return 0

    print("DRY RUN FOUND A BLOCKING CONDITION.")
    print("No production files were changed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
