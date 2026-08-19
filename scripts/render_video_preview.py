import html
import json
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEOS_DIR = ROOT / "data" / "videos"
PREVIEW_DIR = ROOT / "preview-output"

SITE_URL = "https://unitechlk.com"

SITEMAP = ROOT / "sitemap.xml"
VIDEO_SITEMAP = ROOT / "video-sitemap.xml"

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

CATEGORY_HUBS = {
    "powershell": {
        "url": "/powershell/",
        "name": "PowerShell"
    },
    "windows": {
        "url": "/windows/",
        "name": "Windows"
    },
    "windows-storage": {
        "url": "/windows-storage/",
        "name": "Windows Storage"
    },
    "windows-security": {
        "url": "/windows-security/",
        "name": "Windows Security"
    },
    "microsoft-office": {
        "url": "/microsoft-office/",
        "name": "Microsoft Office"
    },
    "printers": {
        "url": "/printers/",
        "name": "Printers"
    },
    "cmd": {
        "url": "/cmd/",
        "name": "CMD"
    },
    "mobile": {
        "url": "/mobile/",
        "name": "Mobile"
    },
}


def esc(value):
    return html.escape(str(value), quote=True)


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


def read_text_if_exists(path):
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8")


def production_status(slug, video_id):
    canonical = f"{SITE_URL}/{slug}/"
    production_file = ROOT / slug / "index.html"

    sitemap_text = read_text_if_exists(SITEMAP)
    video_sitemap_text = read_text_if_exists(VIDEO_SITEMAP)

    return {
        "canonical": canonical,
        "page_exists": production_file.exists(),
        "in_sitemap": canonical in sitemap_text,
        "in_video_sitemap": video_id in video_sitemap_text,
    }


def render_commands(commands):
    if not commands:
        return """
        <section>
          <h2>Steps and Commands</h2>
          <p>No command data was supplied for this tutorial.</p>
        </section>
        """

    # ---------------------------------------------------------
    # WMIC -> PowerShell comparison mode
    # ---------------------------------------------------------

    comparison_mode = any(
        isinstance(item, dict)
        and (
            "wmic" in item
            or "powershell" in item
        )
        for item in commands
    )

    if comparison_mode:
        rows = []

        for item in commands:
            if not isinstance(item, dict):
                continue

            purpose = esc(
                item.get(
                    "purpose",
                    "Command"
                )
            )

            wmic = esc(
                item.get(
                    "wmic",
                    ""
                )
            )

            powershell = esc(
                item.get(
                    "powershell",
                    ""
                )
            )

            rows.append(
                f"""
                <tr>
                  <td>{purpose}</td>
                  <td><code>{wmic}</code></td>
                  <td><code>{powershell}</code></td>
                </tr>
                """
            )

        return f"""
        <section>
          <h2>Commands Used in This Tutorial</h2>

          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Purpose</th>
                  <th>Old WMIC Command</th>
                  <th>PowerShell Replacement</th>
                </tr>
              </thead>

              <tbody>
                {''.join(rows)}
              </tbody>
            </table>
          </div>
        </section>
        """

    # ---------------------------------------------------------
    # General troubleshooting mode
    # ---------------------------------------------------------

    sections = []

    for number, item in enumerate(
        commands,
        start=1
    ):
        if isinstance(item, str):
            purpose = f"Command {number}"
            command = item
            note = ""
            warning = ""

        elif isinstance(item, dict):
            purpose = item.get(
                "purpose",
                f"Step {number}"
            )

            command = item.get(
                "command",
                ""
            )

            note = item.get(
                "note",
                ""
            )

            warning = item.get(
                "warning",
                ""
            )

        else:
            continue

        note_html = ""

        if note:
            note_html = f"""
            <p>
              {esc(note)}
            </p>
            """

        warning_html = ""

        if warning:
            warning_html = f"""
            <div class="command-warning">
              <strong>⚠ Important:</strong>
              <p>{esc(warning)}</p>
            </div>
            """

        sections.append(
            f"""
            <div class="command-step">

              <h3>
                {number}. {esc(purpose)}
              </h3>

              <pre><code>{esc(command)}</code></pre>

              {note_html}

              {warning_html}

            </div>
            """
        )

    return f"""
    <section>

      <h2>Step-by-Step Commands Used in This Tutorial</h2>

      {''.join(sections)}

    </section>
    """


def render_related_guides(guides):
    if not guides:
        return ""

    items = []

    for guide in guides:
        url = f"{SITE_URL}{guide}"

        friendly_name = (
            guide.strip("/")
            .replace("-", " ")
            .title()
        )

        items.append(
            f"""
            <li>
              <a href="{esc(url)}">
                {esc(friendly_name)}
              </a>
            </li>
            """
        )

    return f"""
    <section>
      <h2>Related UniTech LK Guides</h2>

      <ul>
        {''.join(items)}
      </ul>
    </section>
    """


def build_schema(data, category):
    video_id = data["video_id"]
    slug = data["slug"]
    canonical = f"{SITE_URL}/{slug}/"

    duration = seconds_to_iso8601(
        data["duration_seconds"]
    )

    video_schema = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": data["title"],
        "description": data["description"],
        "thumbnailUrl": [
            data["thumbnail_url"]
        ],
        "uploadDate": data["publication_date"],
        "duration": duration,
        "embedUrl": (
            f"https://www.youtube.com/embed/{video_id}"
        ),
        "contentUrl": data["youtube_url"],
    }

    article_schema = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": data["title"],
        "description": data["description"],
        "datePublished": data["publication_date"],
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical,
        },
        "author": {
            "@type": "Organization",
            "name": "UniTech LK",
            "url": SITE_URL,
        },
        "publisher": {
            "@type": "Organization",
            "name": "UniTech LK",
            "url": SITE_URL,
        },
    }

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": f"{SITE_URL}/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": category["name"],
                "item": f"{SITE_URL}{category['url']}",
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": data["title"],
                "item": canonical,
            },
        ],
    }

    return (
        json.dumps(
            video_schema,
            ensure_ascii=False,
            indent=2
        ),
        json.dumps(
            article_schema,
            ensure_ascii=False,
            indent=2
        ),
        json.dumps(
            breadcrumb_schema,
            ensure_ascii=False,
            indent=2
        ),
    )


def render_preview(data):
    video_id = data["video_id"]
    title = data["title"]
    description = data["description"]
    slug = data["slug"]
    category_key = data["category"]

    category = CATEGORY_HUBS.get(category_key)

    if category is None:
        raise ValueError(
            f"Unsupported category: {category_key}"
        )

    status = production_status(
        slug,
        video_id
    )

    (
        video_schema,
        article_schema,
        breadcrumb_schema
    ) = build_schema(
        data,
        category
    )

    commands_html = render_commands(
        data.get("commands", [])
    )

    related_html = render_related_guides(
        data.get("related_guides", [])
    )

    if status["page_exists"]:
        classification = (
            "EXISTING PRODUCTION CONTENT — PROTECTED"
        )
    else:
        classification = "NEW VIDEO GUIDE PREVIEW"

    canonical = status["canonical"]

    return f"""<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">

  <meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
  >

  <!--
    IMPORTANT:
    This file is generated only as a preview.
    It must never be used directly as production output.
  -->

  <meta
    name="robots"
    content="noindex,nofollow,noarchive"
  >

  <title>{esc(title)} | UniTech LK</title>

  <meta
    name="description"
    content="{esc(description)}"
  >

  <link
    rel="canonical"
    href="{esc(canonical)}"
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
    property="og:image"
    content="{esc(data['thumbnail_url'])}"
  >

  <script type="application/ld+json">
{video_schema}
  </script>

  <script type="application/ld+json">
{article_schema}
  </script>

  <script type="application/ld+json">
{breadcrumb_schema}
  </script>

  <style>
    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: #f5f7fa;
      color: #172033;
      line-height: 1.65;
    }}

    header {{
      background: #ffffff;
      border-bottom: 1px solid #dde3ea;
      padding: 18px 24px;
    }}

    header strong {{
      font-size: 22px;
    }}

    main {{
      width: min(1050px, 92%);
      margin: 28px auto 60px;
    }}

    .preview-warning {{
      background: #fff4cc;
      border: 2px solid #e0a800;
      border-radius: 12px;
      padding: 18px;
      margin-bottom: 25px;
    }}

    .preview-warning strong {{
      display: block;
      font-size: 20px;
      margin-bottom: 6px;
    }}

    .command-warning {{
      background: #fff4cc;
      border-left: 5px solid #e0a800;
      padding: 14px 16px;
      margin: 14px 0 24px;
      border-radius: 8px;
    }}

    .status {{
      background: #eef3ff;
      border-left: 5px solid #4169e1;
      padding: 14px 16px;
      margin: 20px 0;
    }}

    article {{
      background: #ffffff;
      border-radius: 14px;
      padding: 28px;
      box-shadow: 0 5px 22px rgba(0, 0, 0, 0.07);
    }}

    h1 {{
      font-size: clamp(30px, 5vw, 48px);
      line-height: 1.12;
      margin-top: 12px;
    }}

    h2 {{
      margin-top: 36px;
      line-height: 1.25;
    }}

    h3 {{
      margin-top: 28px;
    }}

    .breadcrumb {{
      font-size: 14px;
      color: #586174;
      margin-bottom: 12px;
    }}

    .video {{
      position: relative;
      width: 100%;
      padding-top: 56.25%;
      margin: 28px 0;
      border-radius: 12px;
      overflow: hidden;
      background: #000;
    }}

    .video iframe {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      border: 0;
    }}

    .table-wrap {{
      overflow-x: auto;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 20px 0;
    }}

    th,
    td {{
      border: 1px solid #d9dee7;
      text-align: left;
      padding: 12px;
      vertical-align: top;
    }}

    th {{
      background: #f0f3f8;
    }}

    pre {{
      overflow-x: auto;
      background: #111827;
      color: #f8fafc;
      padding: 15px;
      border-radius: 9px;
    }}

    code {{
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, monospace;
    }}

    a {{
      color: #1559c7;
    }}

    footer {{
      text-align: center;
      color: #687386;
      margin-top: 30px;
    }}
  </style>
</head>

<body>

<header>
  <strong>UniTech LK</strong>
</header>

<main>

  <div class="preview-warning">
    <strong>PREVIEW ONLY — NOT PRODUCTION</strong>

    This HTML was generated only for review.
    It is intentionally marked noindex and must not
    replace an existing UniTech LK page automatically.
  </div>

  <article>

    <div class="breadcrumb">
      Home →
      {esc(category["name"])} →
      Preview
    </div>

    <div class="status">
      <strong>Classification:</strong>
      {esc(classification)}
      <br>

      <strong>Metadata enabled:</strong>
      {"YES" if data.get("enabled") is True else "NO"}
      <br>

      <strong>Publish ready:</strong>
      {"YES" if data.get("publish_ready") is True else "NO"}
      <br>

      <strong>Existing page:</strong>
      {"YES" if status["page_exists"] else "NO"}
      <br>

      <strong>Existing sitemap entry:</strong>
      {"YES" if status["in_sitemap"] else "NO"}
      <br>

      <strong>Existing video sitemap entry:</strong>
      {"YES" if status["in_video_sitemap"] else "NO"}
    </div>

    <h1>{esc(title)}</h1>

    <p>
      {esc(description)}
    </p>

    <div class="video">
      <iframe
        src="https://www.youtube.com/embed/{esc(video_id)}"
        title="{esc(title)}"
        loading="lazy"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen
      ></iframe>
    </div>

    <section>
      <h2>About This Tutorial</h2>

      <p>
        {esc(description)}
      </p>
    </section>

    {commands_html}

    {related_html}

  </article>

  <footer>
    Preview generated by the UniTech LK video automation system.
  </footer>

</main>

</body>
</html>
"""


def should_render(path, data):
    if path.name == "example-video.json":
        return False

    video_id = data.get(
        "video_id",
        ""
    )

    if not isinstance(
        video_id,
        str
    ):
        return False

    return bool(
        YOUTUBE_ID_RE.fullmatch(video_id)
    )


def main():
    print("UniTech LK HTML Preview Generator")
    print("================================")
    print("PREVIEW MODE ONLY")
    print()

    if not VIDEOS_DIR.exists():
        print(
            "ERROR: data/videos directory does not exist."
        )
        return 1

    if PREVIEW_DIR.exists():
        shutil.rmtree(
            PREVIEW_DIR
        )

    PREVIEW_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    files = sorted(
        VIDEOS_DIR.glob("*.json")
    )

    rendered = 0

    for path in files:
        try:
            with path.open(
                "r",
                encoding="utf-8"
            ) as handle:
                data = json.load(handle)

        except Exception as exc:
            print(
                f"ERROR reading {path.name}: {exc}"
            )
            return 1

        if not should_render(
            path,
            data
        ):
            print(
                f"SKIP: {path.name}"
            )
            continue

        slug = data["slug"]

        output_dir = (
            PREVIEW_DIR /
            slug
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        output_file = (
            output_dir /
            "index.html"
        )

        try:
            preview_html = render_preview(
                data
            )

        except Exception as exc:
            print(
                f"ERROR rendering {path.name}: {exc}"
            )
            return 1

        output_file.write_text(
            preview_html,
            encoding="utf-8"
        )

        print(
            "PREVIEW CREATED: "
            f"{output_file.relative_to(ROOT)}"
        )

        rendered += 1

    print()
    print("--------------------------------")

    if rendered == 0:
        print(
            "No real video metadata files were available "
            "for preview."
        )
        return 1

    print(
        f"SUCCESS: Generated {rendered} preview file(s)."
    )

    print(
        "Production website files were not modified."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
