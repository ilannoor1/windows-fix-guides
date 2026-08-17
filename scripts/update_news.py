#!/usr/bin/env python3

from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse


SITE_URL = "https://unitechlk.com"

NEWS_ROOT = Path("news")
WINDOWS_DIR = NEWS_ROOT / "windows"
WINDOWS_INDEX = WINDOWS_DIR / "index.html"

STATE_FILE = NEWS_ROOT / ".windows-news-state.json"

MAX_INDEX_ITEMS = 20
MAX_NEW_ARTICLES_PER_RUN = 3

AUTO_START = "<!-- AUTO-NEWS-START -->"
AUTO_END = "<!-- AUTO-NEWS-END -->"

USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; UniTechLK-NewsBot/2.0; "
    "+https://unitechlk.com/news/)"
)


SOURCES = [
    {
        "name": "Windows Blog",
        "publisher": "Microsoft",
        "feed": "https://blogs.windows.com/feed/",
        "allowed_hosts": {
            "blogs.windows.com",
            "www.blogs.windows.com",
        },
    },
]


def log(message: str) -> None:
    print(f"[UniTech LK] {message}")


def escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def clean_text(value: str) -> str:

    if not value:
        return ""

    value = re.sub(
        r"<script.*?</script>",
        " ",
        value,
        flags=re.I | re.S,
    )

    value = re.sub(
        r"<style.*?</style>",
        " ",
        value,
        flags=re.I | re.S,
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = html.unescape(value)

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value


def shorten(text: str, limit: int = 500) -> str:

    text = clean_text(text)

    if len(text) <= limit:
        return text

    result = text[:limit].rsplit(" ", 1)[0]

    return result.strip() + "…"


def slugify(title: str) -> str:

    value = title.lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value,
    )

    value = value.strip("-")

    return value[:90] or "windows-news"


def valid_http_url(url: str) -> bool:

    try:

        parsed = urlparse(url)

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )

    except Exception:

        return False


def host_allowed(
    url: str,
    allowed_hosts: set[str],
) -> bool:

    try:

        hostname = urlparse(url).hostname

        if not hostname:
            return False

        return hostname.lower() in allowed_hosts

    except Exception:

        return False


def parse_date(value: str) -> datetime:

    if not value:
        return datetime.now(timezone.utc)

    try:

        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:
        pass

    try:

        dt = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:

        return datetime.now(
            timezone.utc
        )


def display_date(dt: datetime) -> str:

    return dt.strftime(
        "%B %d, %Y"
    )


def iso_datetime(dt: datetime) -> str:

    return dt.astimezone(
        timezone.utc
    ).isoformat()


def load_state() -> dict:

    if not STATE_FILE.exists():

        return {
            "initialized": False,
            "seen": [],
        }

    try:

        state = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        state.setdefault(
            "initialized",
            False,
        )

        state.setdefault(
            "seen",
            [],
        )

        return state

    except Exception:

        return {
            "initialized": False,
            "seen": [],
        }


def save_state(state: dict) -> None:

    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    state["seen"] = list(
        dict.fromkeys(
            state.get(
                "seen",
                [],
            )
        )
    )[-1000:]

    STATE_FILE.write_text(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def download(url: str) -> bytes:

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml,"
                "application/atom+xml,"
                "application/xml,"
                "text/xml,*/*"
            ),
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:

        return response.read()


def local_name(tag: str) -> str:

    return tag.split("}")[-1].lower()


def child_text(
    element,
    names: set[str],
) -> str:

    for child in list(element):

        if local_name(child.tag) not in names:
            continue

        value = "".join(
            child.itertext()
        ).strip()

        if value:
            return value

    return ""


def entry_link(element) -> str:

    for child in list(element):

        if local_name(child.tag) != "link":
            continue

        href = child.attrib.get(
            "href",
            "",
        ).strip()

        rel = child.attrib.get(
            "rel",
            "alternate",
        ).strip()

        if (
            href
            and rel in {"", "alternate"}
        ):
            return href

        text = "".join(
            child.itertext()
        ).strip()

        if text.startswith(
            ("http://", "https://")
        ):
            return text

    return ""


def parse_feed(source: dict) -> list[dict]:

    log(
        "Checking official source: "
        + source["name"]
    )

    xml_data = download(
        source["feed"]
    )

    root = ET.fromstring(
        xml_data
    )

    articles = []

    for element in root.iter():

        if local_name(
            element.tag
        ) not in {
            "item",
            "entry",
        }:
            continue

        title = child_text(
            element,
            {"title"},
        )

        url = entry_link(
            element
        )

        description = child_text(
            element,
            {
                "description",
                "summary",
                "content",
                "encoded",
            },
        )

        published_raw = child_text(
            element,
            {
                "pubdate",
                "published",
                "updated",
                "date",
            },
        )

        if not title or not url:
            continue

        if not valid_http_url(url):
            continue

        if not host_allowed(
            url,
            source["allowed_hosts"],
        ):

            log(
                "Skipped non-approved URL: "
                + url
            )

            continue

        articles.append(
            {
                "title": clean_text(
                    title
                ),
                "url": url,
                "summary": shorten(
                    description
                ),
                "published": parse_date(
                    published_raw
                ),
                "source": source["name"],
                "publisher": source[
                    "publisher"
                ],
            }
        )

    return articles


def create_article_page(
    article: dict,
) -> tuple[str, bool]:

    title = article["title"]
    source_url = article["url"]
    summary = article["summary"]
    published = article["published"]
    publisher = article["publisher"]
    source_name = article["source"]

    base_slug = slugify(
        title
    )

    slug = base_slug

    counter = 2

    while (
        WINDOWS_DIR
        / slug
        / "index.html"
    ).exists():

        existing_path = (
            WINDOWS_DIR
            / slug
            / "index.html"
        )

        existing = existing_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        if source_url in existing:

            return slug, False

        slug = (
            f"{base_slug}-{counter}"
        )

        counter += 1

    article_dir = (
        WINDOWS_DIR
        / slug
    )

    article_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    canonical = (
        f"{SITE_URL}"
        f"/news/windows/{slug}/"
    )

    description = shorten(
        summary
        or (
            f"Windows update published "
            f"by {publisher}."
        ),
        155,
    )

    article_summary = (
        summary
        or (
            "The official Windows source "
            "has published a new update. "
            "Use the original source link "
            "for complete technical details."
        )
    )

    document = f"""<!DOCTYPE html>
<html lang="en">

<head>

  <meta charset="UTF-8">

  <meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
  >

  <title>{escape(title)} | UniTech LK News</title>

  <meta
    name="description"
    content="{escape(description)}"
  >

  <meta name="author" content="UniTech LK">

  <meta
    name="robots"
    content="index, follow, max-image-preview:large, max-snippet:-1"
  >

  <link
    rel="canonical"
    href="{escape(canonical)}"
  >

  <link
    rel="stylesheet"
    href="/assets/style.css"
  >

  <meta property="og:type" content="article">

  <meta
    property="og:title"
    content="{escape(title)}"
  >

  <meta
    property="og:description"
    content="{escape(description)}"
  >

  <meta
    property="og:url"
    content="{escape(canonical)}"
  >

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": {json.dumps(title)},
    "datePublished": {json.dumps(iso_datetime(published))},
    "dateModified": {json.dumps(iso_datetime(published))},
    "inLanguage": "en",
    "mainEntityOfPage": {{
      "@type": "WebPage",
      "@id": {json.dumps(canonical)}
    }},
    "author": {{
      "@type": "Organization",
      "name": "UniTech LK",
      "url": "https://unitechlk.com/"
    }},
    "publisher": {{
      "@type": "Organization",
      "name": "UniTech LK",
      "url": "https://unitechlk.com/"
    }},
    "isBasedOn": {json.dumps(source_url)}
  }}
  </script>

</head>


<body>

<header>

  <div class="container">

    <a href="/news/windows/">
      ← Windows News
    </a>

  </div>

</header>


<main class="container">

  <article>


    <div class="hero">

      <span class="label">
        Windows News
      </span>

      <h1>
        {escape(title)}
      </h1>

      <p>
        Original publisher:
        <strong>
          {escape(publisher)}
        </strong>
      </p>

      <p>
        Published:
        <strong>
          {escape(display_date(published))}
        </strong>
      </p>

    </div>


    <section class="warning">

      <h2>
        Original Official Source
      </h2>

      <p>
        This page is a short UniTech LK
        summary based on information
        published by
        <strong>
          {escape(publisher)}
        </strong>.
      </p>

      <p>
        UniTech LK is not the original
        publisher of this announcement.
      </p>

      <p>
        Source:
        <strong>
          {escape(source_name)}
        </strong>
      </p>

      <a
        class="button"
        href="{escape(source_url)}"
        target="_blank"
        rel="noopener noreferrer"
      >
        Read Original {escape(publisher)} Article
      </a>

    </section>


    <section>

      <h2>
        Summary
      </h2>

      <p>
        {escape(article_summary)}
      </p>

    </section>


    <section>

      <h2>
        Why This Matters
      </h2>

      <p>
        Windows announcements can
        include feature updates,
        security changes,
        compatibility information,
        known issues or administrator
        guidance.
      </p>

      <p>
        Review the original publisher's
        documentation before making
        important system changes.
      </p>

    </section>


    <section>

      <h2>
        Source &amp; Attribution
      </h2>

      <p>
        Original publisher:
        <strong>
          {escape(publisher)}
        </strong>
      </p>

      <p>
        Original article:
      </p>

      <p>
        <a
          href="{escape(source_url)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          {escape(source_url)}
        </a>
      </p>

    </section>


    <section>

      <h2>
        Related UniTech LK Guides
      </h2>

      <ul class="related-guides">

        <li>
          <a href="/windows/">
            Windows Troubleshooting
          </a>
        </li>

        <li>
          <a href="/windows-security/">
            Windows Security
          </a>
        </li>

        <li>
          <a href="/powershell/">
            PowerShell Guides
          </a>
        </li>

        <li>
          <a href="/news/">
            Technology News
          </a>
        </li>

      </ul>

    </section>


  </article>

</main>


<footer>

  <div class="container">
    © 2026 UniTech LK —
    Windows news and troubleshooting.
  </div>

</footer>


</body>
</html>
"""

    (
        article_dir
        / "index.html"
    ).write_text(
        document,
        encoding="utf-8",
    )

    return slug, True


def find_generated_articles() -> list[dict]:

    articles = []

    if not WINDOWS_DIR.exists():
        return articles

    for directory in WINDOWS_DIR.iterdir():

        if not directory.is_dir():
            continue

        page = (
            directory
            / "index.html"
        )

        if not page.exists():
            continue

        text = page.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        title_match = re.search(
            r"<h1>\s*(.*?)\s*</h1>",
            text,
            flags=re.I | re.S,
        )

        date_match = re.search(
            r'"datePublished"\s*:\s*"([^"]+)"',
            text,
        )

        if not title_match:
            continue

        title = clean_text(
            title_match.group(1)
        )

        if date_match:

            published = parse_date(
                date_match.group(1)
            )

        else:

            published = (
                datetime.fromtimestamp(
                    page.stat().st_mtime,
                    tz=timezone.utc,
                )
            )

        articles.append(
            {
                "title": title,
                "slug": directory.name,
                "published": published,
            }
        )

    articles.sort(
        key=lambda item:
        item["published"],
        reverse=True,
    )

    return articles[
        :MAX_INDEX_ITEMS
    ]


def build_news_cards() -> str:

    articles = (
        find_generated_articles()
    )

    if not articles:

        return """
    <article class="guide-card">

      <span class="label">
        News Monitoring Active
      </span>

      <h2>
        Waiting for the next official Windows update
      </h2>

      <p>
        UniTech LK is monitoring official Windows sources.
        New announcements will automatically appear here.
      </p>

    </article>
"""

    cards = []

    for article in articles:

        cards.append(
            f"""
    <article class="guide-card">

      <span class="label">
        {escape(display_date(article["published"]))}
      </span>

      <h2>

        <a
          href="/news/windows/{escape(article["slug"])}/"
        >
          {escape(article["title"])}
        </a>

      </h2>

      <p>
        Official-source Windows news
        with clear attribution and a
        direct link to the original
        publication.
      </p>

      <a
        class="button"
        href="/news/windows/{escape(article["slug"])}/"
      >
        Read Summary
      </a>

    </article>
"""
        )

    return "\n".join(cards)


def update_windows_index() -> None:

    if not WINDOWS_INDEX.exists():

        log(
            "Windows news index not found. "
            "Skipping index update."
        )

        return

    document = WINDOWS_INDEX.read_text(
        encoding="utf-8"
    )

    if (
        AUTO_START not in document
        or AUTO_END not in document
    ):

        log(
            "AUTO-NEWS markers not found. "
            "Existing Windows hub was preserved."
        )

        return

    generated = build_news_cards()

    pattern = (
        re.escape(AUTO_START)
        + r".*?"
        + re.escape(AUTO_END)
    )

    replacement = (
        AUTO_START
        + "\n"
        + generated
        + "\n"
        + AUTO_END
    )

    new_document = re.sub(
        pattern,
        replacement,
        document,
        count=1,
        flags=re.S,
    )

    if new_document != document:

        WINDOWS_INDEX.write_text(
            new_document,
            encoding="utf-8",
        )

        log(
            "Updated Windows news cards."
        )


def main() -> int:

    WINDOWS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    state = load_state()

    seen = set(
        state.get(
            "seen",
            [],
        )
    )

    all_articles = []

    for source in SOURCES:

        try:

            all_articles.extend(
                parse_feed(source)
            )

        except Exception as error:

            log(
                f"Source failed: "
                f"{source['name']}: "
                f"{error}"
            )

    if not all_articles:

        log(
            "No official feed articles "
            "could be retrieved."
        )

        return 0

    unique = {}

    for article in all_articles:

        unique[
            article["url"]
        ] = article

    all_articles = list(
        unique.values()
    )

    all_articles.sort(
        key=lambda item:
        item["published"],
        reverse=True,
    )


    if not state.get(
        "initialized",
        False,
    ):

        log(
            "First run detected. "
            "Establishing RSS baseline."
        )

        for article in all_articles:

            seen.add(
                article["url"]
            )

        state["seen"] = list(
            seen
        )

        state["initialized"] = True

        save_state(
            state
        )

        update_windows_index()

        log(
            "Baseline complete. "
            "No historical articles "
            "were automatically published."
        )

        return 0


    new_articles = [
        article
        for article in all_articles
        if article["url"]
        not in seen
    ]

    new_articles.sort(
        key=lambda item:
        item["published"]
    )

    new_articles = (
        new_articles[
            :MAX_NEW_ARTICLES_PER_RUN
        ]
    )

    created = 0

    for article in new_articles:

        try:

            slug, was_created = (
                create_article_page(
                    article
                )
            )

            seen.add(
                article["url"]
            )

            if was_created:

                created += 1

                log(
                    "Created news article: "
                    f"/news/windows/{slug}/"
                )

                log(
                    "Original source: "
                    + article["url"]
                )

        except Exception as error:

            log(
                "Article creation failed: "
                + str(error)
            )

    state["seen"] = list(
        seen
    )

    save_state(
        state
    )

    update_windows_index()

    log(
        f"Finished. "
        f"New articles created: {created}"
    )

    return 0


if __name__ == "__main__":

    try:

        sys.exit(
            main()
        )

    except KeyboardInterrupt:

        sys.exit(130)

    except Exception as error:

        print(
            "[UniTech LK] "
            f"Fatal error: {error}",
            file=sys.stderr,
        )

        sys.exit(1)
