import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEOS_DIR = ROOT / "data" / "videos"

SITE_URL = "https://unitechlk.com"

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


def inspect_related_guides(data):
    problems = []

    for guide in data.get("related_guides", []):
        target = local_path_from_url_path(guide)

        if not target.exists():
            problems.append(
                f"Related guide does not exist in repository: {guide}"
            )

    return problems


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

    if data.get("enabled") is not True:
        print("STATUS: DISABLED")
        print("ACTION: SKIP")
        print("No page will be generated.")
        return True

    video_id = data["video_id"]
    title = data["title"]
    slug = data["slug"]
    category = data["category"]
    duration_seconds = data["duration_seconds"]

    hub = CATEGORY_HUBS.get(category)

    if hub is None:
        print(f"BLOCKED: Unknown category '{category}'")
        print("Allowed categories:")
        for allowed in sorted(CATEGORY_HUBS):
            print(f"  - {allowed}")
        return False

    output_dir = ROOT / slug
    output_file = output_dir / "index.html"

    canonical = f"{SITE_URL}/{slug}/"
    embed_url = f"https://www.youtube.com/embed/{video_id}"
    duration_iso = seconds_to_iso8601(duration_seconds)

    print("STATUS: ENABLED")
    print()
    print("DRY-RUN PLAN")
    print("------------")
    print(f"Title:          {title}")
    print(f"Video ID:       {video_id}")
    print(f"Slug:           {slug}")
    print(f"Category:       {category}")
    print(f"Category hub:   {hub}")
    print(f"Canonical URL:  {canonical}")
    print(f"Output file:    {output_file.relative_to(ROOT)}")
    print(f"Embed URL:      {embed_url}")
    print(f"Duration:       {duration_iso}")

    problems = []

    hub_path = local_path_from_url_path(hub)

    if not hub_path.exists():
        problems.append(
            f"Category hub does not exist in repository: {hub}"
        )

    problems.extend(inspect_related_guides(data))

    if output_file.exists():
        problems.append(
            "Target page already exists. Automatic overwrite is blocked."
        )

    if problems:
        print()
        print("SAFETY CHECK: BLOCKED")
        print("---------------------")

        for problem in problems:
            print(f"- {problem}")

        print()
        print("No files were changed.")
        return False

    print()
    print("SAFETY CHECK: PASS")
    print("------------------")
    print("The metadata is eligible for a future guide generation step.")
    print()
    print("Future generator would:")
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
