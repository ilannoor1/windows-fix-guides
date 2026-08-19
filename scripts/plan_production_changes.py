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


def read_text_if_exists(path):
    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8"
    )


def load_json(path):
    with path.open(
        "r",
        encoding="utf-8"
    ) as handle:
        return json.load(handle)


def repository_path_from_url_path(url_path):
    clean = url_path.strip("/")

    if not clean:
        return ROOT

    return ROOT / clean


def relative_display(path):
    try:
        return str(
            path.relative_to(ROOT)
        )
    except ValueError:
        return str(path)


def inspect_existing_production(
    slug,
    video_id,
):
    canonical = (
        f"{SITE_URL}/{slug}/"
    )

    page_file = (
        ROOT /
        slug /
        "index.html"
    )

    sitemap_text = (
        read_text_if_exists(
            SITEMAP
        )
    )

    video_sitemap_text = (
        read_text_if_exists(
            VIDEO_SITEMAP
        )
    )

    return {
        "canonical": canonical,
        "page_file": page_file,
        "page_exists": (
            page_file.exists()
        ),
        "in_sitemap": (
            canonical
            in sitemap_text
        ),
        "video_in_video_sitemap": (
            video_id
            in video_sitemap_text
        ),
    }


def inspect_hub(
    category,
    slug,
):
    hub_url = (
        CATEGORY_HUBS.get(
            category
        )
    )

    if hub_url is None:
        return {
            "known": False,
            "url": None,
            "path": None,
            "index_file": None,
            "exists": False,
            "already_links_page": False,
        }

    hub_path = (
        repository_path_from_url_path(
            hub_url
        )
    )

    hub_index = (
        hub_path /
        "index.html"
    )

    hub_text = (
        read_text_if_exists(
            hub_index
        )
    )

    expected_href = (
        f"/{slug}/"
    )

    return {
        "known": True,
        "url": hub_url,
        "path": hub_path,
        "index_file": hub_index,
        "exists": (
            hub_index.exists()
        ),
        "already_links_page": (
            expected_href
            in hub_text
        ),
    }


def inspect_related_guides(
    data,
):
    missing = []

    for guide in data.get(
        "related_guides",
        []
    ):
        target = (
            repository_path_from_url_path(
                guide
            )
        )

        index_file = (
            target /
            "index.html"
        )

        if not index_file.exists():
            missing.append(
                guide
            )

    return missing


def duplicate_metadata_problems(
    metadata_records,
):
    problems = []

    seen_slugs = {}
    seen_video_ids = {}

    for path, data in metadata_records:
        slug = data.get(
            "slug",
            ""
        )

        video_id = data.get(
            "video_id",
            ""
        )

        if slug:
            if slug in seen_slugs:
                problems.append(
                    "Duplicate slug "
                    f"'{slug}' in "
                    f"{relative_display(seen_slugs[slug])} "
                    "and "
                    f"{relative_display(path)}"
                )
            else:
                seen_slugs[slug] = path

        if video_id:
            if video_id in seen_video_ids:
                problems.append(
                    "Duplicate video_id "
                    f"'{video_id}' in "
                    f"{relative_display(seen_video_ids[video_id])} "
                    "and "
                    f"{relative_display(path)}"
                )
            else:
                seen_video_ids[
                    video_id
                ] = path

    return problems


def print_existing_status(
    existing,
    hub,
):
    print()
    print("CURRENT PRODUCTION STATE")
    print("------------------------")

    print(
        "Page exists:              "
        f"{'YES' if existing['page_exists'] else 'NO'}"
    )

    print(
        "Normal sitemap entry:     "
        f"{'YES' if existing['in_sitemap'] else 'NO'}"
    )

    print(
        "Video sitemap entry:      "
        f"{'YES' if existing['video_in_video_sitemap'] else 'NO'}"
    )

    if hub["known"]:
        print(
            "Category hub exists:     "
            f"{'YES' if hub['exists'] else 'NO'}"
        )

        print(
            "Hub already links page:  "
            f"{'YES' if hub['already_links_page'] else 'NO'}"
        )


def production_exists(
    existing,
):
    return any(
        [
            existing[
                "page_exists"
            ],
            existing[
                "in_sitemap"
            ],
            existing[
                "video_in_video_sitemap"
            ],
        ]
    )


def plan_one(
    path,
    data,
):
    print()
    print("=" * 72)

    print(
        f"Metadata: "
        f"{relative_display(path)}"
    )

    print("=" * 72)

    enabled = (
        data.get("enabled")
        is True
    )

    slug = data.get(
        "slug",
        ""
    )

    video_id = data.get(
        "video_id",
        ""
    )

    category = data.get(
        "category",
        ""
    )

    title = data.get(
        "title",
        ""
    )

    print(
        f"Enabled:     "
        f"{'YES' if enabled else 'NO'}"
    )

    print(
        f"Title:       "
        f"{title}"
    )

    print(
        f"Video ID:    "
        f"{video_id}"
    )

    print(
        f"Slug:        "
        f"{slug}"
    )

    print(
        f"Category:    "
        f"{category}"
    )

    existing = (
        inspect_existing_production(
            slug,
            video_id,
        )
    )

    hub = inspect_hub(
        category,
        slug,
    )

    print_existing_status(
        existing,
        hub,
    )

    # ---------------------------------------------------------
    # DISABLED METADATA
    # ---------------------------------------------------------

    if not enabled:
        print()
        print("PUBLISH STATE")
        print("-------------")

        if production_exists(
            existing
        ):
            print(
                "CLASSIFICATION: "
                "EXISTING PRODUCTION CONTENT"
            )

            print(
                "PROTECTION: LOCKED"
            )

            print()
            print("PROTECT:")

            if existing[
                "page_exists"
            ]:
                print(
                    "  - "
                    f"{relative_display(existing['page_file'])}"
                )

            if existing[
                "in_sitemap"
            ]:
                print(
                    "  - sitemap.xml entry"
                )

            if existing[
                "video_in_video_sitemap"
            ]:
                print(
                    "  - video-sitemap.xml entry"
                )

            print()
            print(
                "ACTION: NO PRODUCTION CHANGE"
            )

            print(
                "Existing content must "
                "not be overwritten."
            )

        else:
            print(
                "CLASSIFICATION: "
                "NEW / UNPUBLISHED DRAFT"
            )

            print()
            print(
                "ACTION: NO PRODUCTION CHANGE"
            )

            print(
                "Metadata is disabled."
            )

        print()
        print(
            "NO FILES WERE CHANGED."
        )

        return True

    # ---------------------------------------------------------
    # ENABLED METADATA
    # ---------------------------------------------------------

    print()
    print("PUBLISH STATE")
    print("-------------")
    print(
        "CLASSIFICATION: "
        "ENABLED FOR PLANNING"
    )

    problems = []

    # Unknown category.
    if not hub["known"]:
        problems.append(
            "Unknown category "
            f"'{category}'."
        )

    # Existing production content.
    if production_exists(
        existing
    ):
        problems.append(
            "Existing production "
            "content detected."
        )

    # Hub must exist.
    if (
        hub["known"]
        and not hub["exists"]
    ):
        problems.append(
            "Category hub index.html "
            "does not exist: "
            f"{hub['url']}"
        )

    # Related guides must exist.
    missing_guides = (
        inspect_related_guides(
            data
        )
    )

    for guide in missing_guides:
        problems.append(
            "Related guide does "
            f"not exist: {guide}"
        )

    # Production target should not exist.
    target_page = (
        ROOT /
        slug /
        "index.html"
    )

    if target_page.exists():
        problems.append(
            "Target production page "
            "already exists."
        )

    # ---------------------------------------------------------
    # BLOCK IF ANY SAFETY ISSUE EXISTS
    # ---------------------------------------------------------

    if problems:
        print()
        print("PRODUCTION PLAN: BLOCKED")
        print("------------------------")

        for problem in problems:
            print(
                f"- {problem}"
            )

        print()
        print(
            "No automatic production "
            "publishing is permitted."
        )

        print(
            "NO FILES WERE CHANGED."
        )

        return False

    # ---------------------------------------------------------
    # SIMULATED PRODUCTION DIFF
    # ---------------------------------------------------------

    print()
    print("PRODUCTION PLAN: PASS")
    print("---------------------")

    print()
    print("CREATE:")

    print(
        "  + "
        f"{slug}/index.html"
    )

    print()
    print("MODIFY:")

    if not hub[
        "already_links_page"
    ]:
        print(
            "  ~ "
            f"{relative_display(hub['index_file'])}"
        )
    else:
        print(
            "  = Category hub already "
            "contains this page link"
        )

    print(
        "  ~ sitemap.xml"
    )

    print(
        "  ~ video-sitemap.xml"
    )

    print()
    print("PROTECT:")

    print(
        "  🔒 All existing guide pages"
    )

    print(
        "  🔒 Existing sitemap entries"
    )

    print(
        "  🔒 Existing video sitemap entries"
    )

    print()
    print("EXPECTED NEW URL:")

    print(
        "  "
        f"{existing['canonical']}"
    )

    print()
    print(
        "This is a simulation only."
    )

    print(
        "NO FILES WERE CHANGED."
    )

    return True


def main():
    print(
        "UniTech LK Production Change Planner"
    )

    print(
        "===================================="
    )

    print(
        "MODE: READ-ONLY SIMULATION"
    )

    print(
        "This script never writes "
        "production files."
    )

    print()

    if not VIDEOS_DIR.exists():
        print(
            "ERROR: Missing "
            "data/videos directory."
        )

        return 1

    metadata_paths = sorted(
        VIDEOS_DIR.glob(
            "*.json"
        )
    )

    if not metadata_paths:
        print(
            "ERROR: No metadata "
            "JSON files found."
        )

        return 1

    records = []

    for path in metadata_paths:
        try:
            data = load_json(
                path
            )
        except Exception as exc:
            print(
                "ERROR: Unable to read "
                f"{relative_display(path)}: "
                f"{exc}"
            )

            return 1

        records.append(
            (
                path,
                data,
            )
        )

    duplicate_problems = (
        duplicate_metadata_problems(
            records
        )
    )

    if duplicate_problems:
        print(
            "GLOBAL SAFETY CHECK: FAILED"
        )

        print(
            "---------------------------"
        )

        for problem in duplicate_problems:
            print(
                f"- {problem}"
            )

        print()
        print(
            "Production planning stopped."
        )

        return 1

    print(
        f"Found {len(records)} "
        "metadata file(s)."
    )

    all_ok = True

    for path, data in records:
        result = plan_one(
            path,
            data,
        )

        if not result:
            all_ok = False

    print()
    print("=" * 72)

    if all_ok:
        print(
            "PRODUCTION CHANGE "
            "SIMULATION COMPLETE."
        )

        print(
            "No production files "
            "were changed."
        )

        return 0

    print(
        "PRODUCTION CHANGE "
        "SIMULATION FOUND "
        "A BLOCKING CONDITION."
    )

    print(
        "No production files "
        "were changed."
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())
