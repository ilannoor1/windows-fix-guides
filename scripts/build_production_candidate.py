import html
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VIDEOS_DIR = ROOT / "data" / "videos"
CANDIDATE_DIR = ROOT / "candidate-output"

SITE_URL = "https://unitechlk.com"

SITEMAP = ROOT / "sitemap.xml"
VIDEO_SITEMAP = ROOT / "video-sitemap.xml"

CATEGORY_HUBS = {
    "powershell": {
        "url": "/powershell/",
        "name": "PowerShell",
    },
    "windows": {
        "url": "/windows/",
        "name": "Windows",
    },
    "windows-storage": {
        "url": "/windows-storage/",
        "name": "Windows Storage",
    },
    "windows-security": {
        "url": "/windows-security/",
        "name": "Windows Security",
    },
    "microsoft-office": {
        "url": "/microsoft-office/",
        "name": "Microsoft Office",
    },
    "printers": {
        "url": "/printers/",
        "name": "Printers",
    },
    "cmd": {
        "url": "/cmd/",
        "name": "CMD",
    },
    "mobile": {
        "url": "/mobile/",
        "name": "Mobile",
    },
}


def esc(value):
    return html.escape(
        str(value),
        quote=True,
    )


def load_json(path):
    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


def read_text(path):
    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8"
    )


def seconds_to_iso8601(seconds):
    minutes, secs = divmod(
        seconds,
        60,
    )

    hours, minutes = divmod(
        minutes,
        60,
    )

    result = "PT"

    if hours:
        result += f"{hours}H"

    if minutes:
        result += f"{minutes}M"

    if secs or result == "PT":
        result += f"{secs}S"

    return result


def production_conflicts(
    slug,
    video_id,
):
    canonical = (
        f"{SITE_URL}/{slug}/"
    )

    page = (
        ROOT /
        slug /
        "index.html"
    )

    sitemap_text = read_text(
        SITEMAP
    )

    video_sitemap_text = read_text(
        VIDEO_SITEMAP
    )

    conflicts = []

    if page.exists():
        conflicts.append(
            f"Production page already exists: "
            f"{slug}/index.html"
        )

    if canonical in sitemap_text:
        conflicts.append(
            "Canonical URL already exists "
            "in sitemap.xml"
        )

    if video_id in video_sitemap_text:
        conflicts.append(
            "Video ID already exists "
            "in video-sitemap.xml"
        )

    return conflicts


def related_guides_exist(
    guides,
):
    missing = []

    for guide in guides:
        clean = guide.strip("/")

        target = (
            ROOT /
            clean /
            "index.html"
        )

        if not target.exists():
            missing.append(
                guide
            )

    return missing


def render_commands(commands):
    if not commands:
        return """
<section>
  <h2>Steps and Commands</h2>

  <p>
    No command list was supplied for this tutorial.
  </p>
</section>
"""

    rows = []

    for command in commands:

        if isinstance(
            command,
            dict,
        ):
            purpose = esc(
                command.get(
                    "purpose",
                    "Command",
                )
            )

            old_command = esc(
                command.get(
                    "wmic",
                    "",
                )
            )

            new_command = esc(
                command.get(
                    "powershell",
                    "",
                )
            )

            rows.append(
                f"""
<tr>
  <td>{purpose}</td>
  <td><code>{old_command}</code></td>
  <td><code>{new_command}</code></td>
</tr>
"""
            )

        else:
            rows.append(
                f"""
<tr>
  <td>Command</td>
  <td colspan="2">
    <code>{esc(command)}</code>
  </td>
</tr>
"""
            )

    return f"""
<section>

  <h2>Commands Used in This Tutorial</h2>

  <div style="overflow-x:auto;">

    <table>

      <thead>
        <tr>
          <th>Purpose</th>
          <th>Previous / Old Command</th>
          <th>Current Command</th>
        </tr>
      </thead>

      <tbody>
        {''.join(rows)}
      </tbody>

    </table>

  </div>

</section>
"""


def render_related_guides(guides):
    if not guides:
        return ""

    items = []

    for guide in guides:
        items.append(
            f"""
<li>
  <a href="{esc(guide)}">
    {esc(guide)}
  </a>
</li>
"""
        )

    return f"""
<section>

  <h2>Related UniTech LK Guides</h2>

  <ul class="related-guides">
    {''.join(items)}
  </ul>

</section>
"""


def build_schema(
    data,
    category,
):
    video_id = data[
        "video_id"
    ]

    slug = data[
        "slug"
    ]

    canonical = (
        f"{SITE_URL}/{slug}/"
    )

    duration = (
        seconds_to_iso8601(
            data[
                "duration_seconds"
            ]
        )
    )

    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": (
                    f"{SITE_URL}/"
                    "#organization"
                ),
                "name": "UniTech LK",
                "url": (
                    f"{SITE_URL}/"
                ),
            },
            {
                "@type": "WebSite",
                "@id": (
                    f"{SITE_URL}/"
                    "#website"
                ),
                "url": (
                    f"{SITE_URL}/"
                ),
                "name": "UniTech LK",
                "publisher": {
                    "@id": (
                        f"{SITE_URL}/"
                        "#organization"
                    )
                },
            },
            {
                "@type": "TechArticle",
                "@id": (
                    f"{canonical}"
                    "#article"
                ),
                "headline": (
                    data[
                        "title"
                    ]
                ),
                "description": (
                    data[
                        "description"
                    ]
                ),
                "datePublished": (
                    data[
                        "publication_date"
                    ]
                ),
                "author": {
                    "@id": (
                        f"{SITE_URL}/"
                        "#organization"
                    )
                },
                "publisher": {
                    "@id": (
                        f"{SITE_URL}/"
                        "#organization"
                    )
                },
                "mainEntityOfPage": {
                    "@id": (
                        f"{canonical}"
                        "#webpage"
                    )
                },
            },
            {
                "@type": "WebPage",
                "@id": (
                    f"{canonical}"
                    "#webpage"
                ),
                "url": canonical,
                "name": (
                    data[
                        "title"
                    ]
                ),
                "isPartOf": {
                    "@id": (
                        f"{SITE_URL}/"
                        "#website"
                    )
                },
            },
            {
                "@type": "VideoObject",
                "@id": (
                    f"{canonical}"
                    "#video"
                ),
                "name": (
                    data[
                        "title"
                    ]
                ),
                "description": (
                    data[
                        "description"
                    ]
                ),
                "thumbnailUrl": [
                    data[
                        "thumbnail_url"
                    ]
                ],
                "uploadDate": (
                    data[
                        "publication_date"
                    ]
                ),
                "duration": duration,
                "embedUrl": (
                    "https://www.youtube.com/embed/"
                    f"{video_id}"
                ),
                "contentUrl": (
                    data[
                        "youtube_url"
                    ]
                ),
            },
            {
                "@type": "BreadcrumbList",
                "@id": (
                    f"{canonical}"
                    "#breadcrumb"
                ),
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "UniTech LK",
                        "item": (
                            f"{SITE_URL}/"
                        ),
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": (
                            category[
                                "name"
                            ]
                        ),
                        "item": (
                            f"{SITE_URL}"
                            f"{category['url']}"
                        ),
                    },
                    {
                        "@type": "ListItem",
                        "position": 3,
                        "name": (
                            data[
                                "title"
                            ]
                        ),
                        "item": canonical,
                    },
                ],
            },
        ],
    }

    return json.dumps(
        graph,
        ensure_ascii=False,
        indent=2,
    )


def render_candidate(
    data,
    category,
):
    title = data[
        "title"
    ]

    description = data[
        "description"
    ]

    slug = data[
        "slug"
    ]

    video_id = data[
        "video_id"
    ]

    canonical = (
        f"{SITE_URL}/{slug}/"
    )

    schema = build_schema(
        data,
        category,
    )

    commands_html = (
        render_commands(
            data.get(
                "commands",
                [],
            )
        )
    )

    related_html = (
        render_related_guides(
            data.get(
                "related_guides",
                [],
            )
        )
    )

    return f"""<!DOCTYPE html>
<html lang="en">

<head>

  <meta charset="UTF-8">

  <meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
  >

  <!--
    PRODUCTION CANDIDATE
    Generated for review.
    Not yet committed to the live website.
  -->

  <title>{esc(title)} | UniTech LK</title>

  <meta
    name="description"
    content="{esc(description)}"
  >

  <meta name="author" content="UniTech LK">

  <meta
    name="robots"
    content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"
  >

  <meta name="theme-color" content="#061225">

  <link
    rel="canonical"
    href="{esc(canonical)}"
  >

  <link
    rel="stylesheet"
    href="/assets/style.css"
  >

  <meta
    property="og:type"
    content="article"
  >

  <meta
    property="og:title"
    content="{esc(title)}"
  >

  <meta
    property="og:description"
    content="{esc(description)}"
  >

  <meta
    property="og:url"
    content="{esc(canonical)}"
  >

  <meta
    property="og:site_name"
    content="UniTech LK"
  >

  <meta
    property="og:image"
    content="{esc(data['thumbnail_url'])}"
  >

  <meta
    name="twitter:card"
    content="summary_large_image"
  >

  <meta
    name="twitter:title"
    content="{esc(title)}"
  >

  <meta
    name="twitter:description"
    content="{esc(description)}"
  >

  <meta
    name="twitter:image"
    content="{esc(data['thumbnail_url'])}"
  >

  <script type="application/ld+json">
{schema}
  </script>

</head>


<body>

<header>

  <div class="container">

    <a href="{esc(category['url'])}">
      ← UniTech LK {esc(category['name'])} Guides
    </a>

  </div>

</header>


<main class="container">

  <div class="hero">

    <span class="label">
      {esc(category['name'])} • UniTech LK
    </span>

    <h1>
      {esc(title)}
    </h1>

    <p class="intro">
      {esc(description)}
    </p>

  </div>


  <section>

    <h2>Video Tutorial</h2>

    <div class="video-wrap">

      <iframe
        src="https://www.youtube.com/embed/{esc(video_id)}"
        title="{esc(title)}"
        width="560"
        height="315"
        loading="lazy"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen
      ></iframe>

    </div>

  </section>


  <section>

    <h2>About This Tutorial</h2>

    <p>
      {esc(description)}
    </p>

  </section>


  {commands_html}


  {related_html}


  <a
    class="back-home"
    href="{esc(category['url'])}"
  >
    ← Back to {esc(category['name'])} Guides
  </a>

</main>


<footer>

  <div class="container">
    © 2026 UniTech LK — Windows and IT troubleshooting guides.
  </div>

</footer>

</body>
</html>
"""


def build_candidate(
    metadata_path,
    data,
):
    enabled = (
        data.get(
            "enabled"
        )
        is True
    )

    publish_ready = (
        data.get(
            "publish_ready"
        )
        is True
    )

    if not enabled:
        print(
            f"SKIP: {metadata_path.name} "
            "(enabled=false)"
        )

        return True, None

    if not publish_ready:
        print(
            f"SKIP: {metadata_path.name} "
            "(publish_ready=false)"
        )

        return True, None

    slug = data[
        "slug"
    ]

    video_id = data[
        "video_id"
    ]

    category_key = data[
        "category"
    ]

    category = (
        CATEGORY_HUBS.get(
            category_key
        )
    )

    if category is None:
        print(
            f"BLOCKED: Unknown category "
            f"'{category_key}'"
        )

        return False, None

    conflicts = (
        production_conflicts(
            slug,
            video_id,
        )
    )

    if conflicts:
        print()
        print(
            f"BLOCKED: {metadata_path.name}"
        )

        for conflict in conflicts:
            print(
                f"- {conflict}"
            )

        return False, None

    hub_file = (
        ROOT /
        category["url"].strip("/") /
        "index.html"
    )

    if not hub_file.exists():
        print(
            "BLOCKED: Category hub "
            "does not exist."
        )

        return False, None

    missing_guides = (
        related_guides_exist(
            data.get(
                "related_guides",
                [],
            )
        )
    )

    if missing_guides:
        print(
            "BLOCKED: Missing "
            "related guides:"
        )

        for guide in missing_guides:
            print(
                f"- {guide}"
            )

        return False, None

    output_dir = (
        CANDIDATE_DIR /
        slug
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        output_dir /
        "index.html"
    )

    candidate_html = (
        render_candidate(
            data,
            category,
        )
    )

    output_file.write_text(
        candidate_html,
        encoding="utf-8",
    )

    manifest = {
        "video_id": video_id,
        "slug": slug,
        "title": (
            data[
                "title"
            ]
        ),
        "canonical_url": (
            f"{SITE_URL}/{slug}/"
        ),
        "category": category_key,
        "category_hub": (
            category[
                "url"
            ]
        ),
        "create": [
            f"{slug}/index.html"
        ],
        "modify": [
            str(
                hub_file.relative_to(
                    ROOT
                )
            ),
            "sitemap.xml",
            "video-sitemap.xml",
        ],
        "protected": [
            "all existing guide pages",
            "existing sitemap entries",
            "existing video sitemap entries",
        ],
        "production_status": (
            "CANDIDATE ONLY"
        ),
    }

    manifest_file = (
        output_dir /
        "candidate-manifest.json"
    )

    manifest_file.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "PRODUCTION CANDIDATE BUILT"
    )

    print(
        "--------------------------"
    )

    print(
        f"Metadata: "
        f"{metadata_path.relative_to(ROOT)}"
    )

    print(
        f"Candidate page: "
        f"{output_file.relative_to(ROOT)}"
    )

    print(
        f"Manifest: "
        f"{manifest_file.relative_to(ROOT)}"
    )

    print()
    print(
        "NO LIVE WEBSITE FILES "
        "WERE CHANGED."
    )

    return True, output_file


def main():
    print(
        "UniTech LK Production Candidate Builder"
    )

    print(
        "======================================="
    )

    print(
        "MODE: CANDIDATE OUTPUT ONLY"
    )

    print(
        "Requires enabled=true "
        "AND publish_ready=true."
    )

    print()

    if not VIDEOS_DIR.exists():
        print(
            "ERROR: data/videos "
            "does not exist."
        )

        return 1

    if CANDIDATE_DIR.exists():
        shutil.rmtree(
            CANDIDATE_DIR
        )

    CANDIDATE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata_files = sorted(
        VIDEOS_DIR.glob(
            "*.json"
        )
    )

    if not metadata_files:
        print(
            "ERROR: No metadata "
            "files found."
        )

        return 1

    all_ok = True
    built = 0

    for metadata_path in metadata_files:

        try:
            data = load_json(
                metadata_path
            )

        except Exception as exc:
            print(
                f"ERROR: "
                f"{metadata_path.name}: "
                f"{exc}"
            )

            all_ok = False
            continue

        success, candidate = (
            build_candidate(
                metadata_path,
                data,
            )
        )

        if not success:
            all_ok = False

        if candidate is not None:
            built += 1

    print()
    print(
        "======================================="
    )

    if not all_ok:
        print(
            "FAILED: A production candidate "
            "was blocked by a safety check."
        )

        return 1

    if built == 0:
        print(
            "SUCCESS: No metadata is currently "
            "approved for production candidate generation."
        )

        print(
            "All live website files remain unchanged."
        )

        return 0

    print(
        f"SUCCESS: Built {built} "
        "production candidate(s)."
    )

    print(
        "Human review is required "
        "before any repository write."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
