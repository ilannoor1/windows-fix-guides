#!/usr/bin/env python3

"""
UniTech LK Automatic Windows News Updater

Purpose:
- Read official Microsoft Windows RSS feeds.
- Detect new official Windows articles.
- Create short UniTech LK summary pages.
- Preserve the EXACT original Microsoft source URL.
- Update the Windows news index.
- Avoid copying full source articles.
- Avoid duplicate articles.

Generated pages:
https://unitechlk.com/news/windows/<slug>/
"""

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


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

SITE_URL = "https://unitechlk.com"

NEWS_ROOT = Path("news")
WINDOWS_DIR = NEWS_ROOT / "windows"
STATE_FILE = NEWS_ROOT / ".windows-news-state.json"

MAX_INDEX_ITEMS = 30
MAX_NEW_ARTICLES_PER_RUN = 3

USER_AGENT = (
    "Mozilla/5.0 (compatible; UniTechLK-NewsBot/1.0; "
    "+https://unitechlk.com/news/)"
)


# ---------------------------------------------------------
# OFFICIAL SOURCES ONLY
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# BASIC HELPERS
# ---------------------------------------------------------

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

    value = re.sub(r"<[^>]+>", " ", value)

    value = html.unescape(value)

    value = re.sub(r"\s+", " ", value).strip()

    return value


def shorten(text: str, limit: int = 550) -> str:
    text = clean_text(text)

    if len(text) <= limit:
        return text

    shortened = text[:limit].rsplit(" ", 1)[0].strip()

    return shortened + "…"


def slugify(title: str) -> str:
    value = title.lower()

    value = re.sub(r"[^a-z0-9]+", "-", value)

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


def host_allowed(url: str, allowed_hosts: set[str]) -> bool:
    try:
        host = urlparse(url).hostname

        if not host:
            return False

        host = host.lower()

        return host in allowed_hosts

    except Exception:
        return False


# ---------------------------------------------------------
# DATE HANDLING
# ---------------------------------------------------------

def parse_date(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    try:
        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        pass

    try:
        value = value.replace("Z", "+00:00")

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return datetime.now(timezone.utc)


def display_date(dt: datetime) -> str:
    return dt.strftime("%B %d, %Y")


def iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def iso_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


# ---------------------------------------------------------
# STATE / DUPLICATE PROTECTION
# ---------------------------------------------------------

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {
            "initialized": False,
            "seen": [],
        }

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(data, dict):
            raise ValueError("Invalid state")

        data.setdefault("initialized", False)
        data.setdefault("seen", [])

        return data

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

    # Prevent unlimited file growth.
    state["seen"] = list(
        dict.fromkeys(state.get("seen", []))
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


# ---------------------------------------------------------
# DOWNLOAD RSS
# ---------------------------------------------------------

def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml,"
                "application/atom+xml,"
                "application/xml,text/xml,*/*"
            ),
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        return response.read()


# ---------------------------------------------------------
# XML HELPERS
# ---------------------------------------------------------

def local_name(tag: str) -> str:
    return tag.split("}")[-1].lower()


def child_text(element, names: set[str]) -> str:
    for child in list(element):

        if local_name(child.tag) in names:

            text = "".join(
                child.itertext()
            ).strip()

            if text:
                return text

    return ""


def entry_link(element) -> str:
    # RSS <link>URL</link>
    for child in list(element):

        if local_name(child.tag) != "link":
            continue

        href = child.attrib.get("href", "").strip()

        rel = child.attrib.get("rel", "alternate").strip()

        if href and rel in {"", "alternate"}:
            return href

        text = "".join(
            child.itertext()
        ).strip()

        if text.startswith(("http://", "https://")):
            return text

    return ""


# ---------------------------------------------------------
# PARSE RSS / ATOM
# ---------------------------------------------------------

def parse_feed(source: dict) -> list[dict]:
    log(f"Checking official source: {source['name']}")

    xml_data = download(source["feed"])

    root = ET.fromstring(xml_data)

    articles = []

    for element in root.iter():

        name = local_name(element.tag)

        if name not in {"item", "entry"}:
            continue

        title = child_text(
            element,
            {"title"},
        )

        url = entry_link(element)

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

        # SECURITY / SOURCE INTEGRITY:
        # Do not publish an item pretending to be Microsoft
        # if the RSS item points outside approved Microsoft hosts.
        if not host_allowed(
            url,
            source["allowed_hosts"],
        ):
            log(
                "Skipped non-approved source URL: "
                + url
            )
            continue

        published = parse_date(published_raw)

        articles.append(
            {
                "title": clean_text(title),
                "url": url,
                "summary": shorten(description),
                "published": published,
                "source": source["name"],
                "publisher": source["publisher"],
            }
        )

    return articles


# ---------------------------------------------------------
# ARTICLE PAGE
# ---------------------------------------------------------

def create_article_page(article: dict) -> tuple[str, str]:

    title = article["title"]
    source_url = article["url"]
    summary = article["summary"]
    published = article["published"]
    publisher = article["publisher"]
    source_name = article["source"]

    base_slug = slugify(title)

    slug = base_slug

    counter = 2

    while (
        WINDOWS_DIR / slug / "index.html"
    ).exists():

        existing_file = (
            WINDOWS_DIR
            / slug
            / "index.html"
        )

        existing = existing_file.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        if source_url in existing:
            return slug, "existing"

        slug = f"{base_slug}-{counter}"
        counter += 1

    article_dir = WINDOWS_DIR / slug

    article_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    canonical = (
        f"{SITE_URL}/news/windows/{slug}/"
    )

    meta_description = (
        summary
        or (
            f"UniTech LK summary of the latest "
            f"Windows update published by {publisher}."
        )
    )

    meta_description = shorten(
        meta_description,
        155,
    )

    page_summary = summary or (
        "The official source has published a new Windows "
        "update. Use the original source link below for the "
        "complete announcement and technical information."
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
    content="{escape(meta_description)}"
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
    content="{escape(meta_description)}"
  >

  <meta
    property="og:url"
    content="{escape(canonical)}"
  >

  <meta
    property="article:published_time"
    content="{escape(iso_datetime(published))}"
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

      <h1>{escape(title)}</h1>

      <p>
        Published by the original source:
        <strong>{escape(publisher)}</strong>
      </p>

      <p>
        Original publication date:
        <strong>{escape(display_date(published))}</strong>
      </p>

    </div>


    <section class="warning">

      <h2>Original Source</h2>

      <p>
        This page is a short UniTech LK summary of information
        published by {escape(publisher)}.
        UniTech LK is not the original publisher of this announcement.
      </p>

      <p>
        <strong>Source:</strong>
        {escape(source_name)}
      </p>

      <p>
        <a
          class="button"
          href="{escape(source_url)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          Read the Original {escape(publisher)} Article
        </a>
      </p>

    </section>


    <section>

      <h2>Summary</h2>

      <p>
        {escape(page_summary)}
      </p>

    </section>


    <section>

      <h2>Why This Matters</h2>

      <p>
        Windows announcements can include operating-system
        updates, security changes, feature rollouts,
        compatibility information and administrator guidance.
      </p>

      <p>
        Check the original source before installing,
        removing or changing important system components.
      </p>

    </section>


    <section>

      <h2>Source and Attribution</h2>

      <p>
        Original publisher:
        <strong>{escape(publisher)}</strong>
      </p>

      <p>
        UniTech LK provides this page for news discovery,
        technical context and troubleshooting awareness.
        The complete original information remains available
        from the publisher.
      </p>

      <p>
        <a
          href="{escape(source_url)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          View original source
        </a>
      </p>

    </section>


    <section>

      <h2>Related UniTech LK Resources</h2>

      <ul class="related-guides">

        <li>
          <a href="/windows/">
            Windows Troubleshooting Guides
          </a>
        </li>

        <li>
          <a href="/windows-security/">
            Windows Security Guides
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
    © 2026 UniTech LK — Windows news and troubleshooting.
  </div>
</footer>

</body>
</html>
"""

    (article_dir / "index.html").write_text(
        document,
        encoding="utf-8",
    )

    return slug, "created"


# ---------------------------------------------------------
# WINDOWS NEWS INDEX
# ---------------------------------------------------------

def find_generated_articles() -> list[dict]:

    articles = []

    if not WINDOWS_DIR.exists():
        return articles

    for path in WINDOWS_DIR.iterdir():

        if not path.is_dir():
            continue

        page = path / "index.html"

        if not page.exists():
            continue

        text = page.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        title_match = re.search(
            r"<h1>(.*?)</h1>",
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
            published = datetime.fromtimestamp(
                page.stat().st_mtime,
                tz=timezone.utc,
            )

        articles.append(
            {
                "title": title,
                "slug": path.name,
                "published": published,
            }
        )

    articles.sort(
        key=lambda item: item["published"],
        reverse=True,
    )

    return articles[:MAX_INDEX_ITEMS]


def update_windows_index() -> None:

    articles = find_generated_articles()

    cards = []

    for article in articles:

        cards.append(
            f"""
      <article class="guide-card">

        <span class="label">
          {escape(display_date(article["published"]))}
        </span>

        <h2>
          <a href="/news/windows/{escape(article["slug"])}/">
            {escape(article["title"])}
          </a>
        </h2>

        <p>
          Latest Windows information from an official source,
          with attribution and a direct link to the original
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

    if cards:
        cards_html = "\n".join(cards)
    else:
        cards_html = """
      <article class="guide-card">
        <h2>Windows News Monitoring Active</h2>
        <p>
          UniTech LK is checking official Windows sources.
          New items will appear here after they are detected.
        </p>
      </article>
"""

    index_document = f"""<!DOCTYPE html>
<html lang="en">
<head>

  <meta charset="UTF-8">

  <meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
  >

  <title>Windows News & Updates | UniTech LK</title>

  <meta
    name="description"
    content="Latest Windows news, Microsoft updates, security information and official Windows announcements with direct links to original sources."
  >

  <meta name="author" content="UniTech LK">

  <meta
    name="robots"
    content="index, follow, max-image-preview:large"
  >

  <link
    rel="canonical"
    href="https://unitechlk.com/news/windows/"
  >

  <link
    rel="stylesheet"
    href="/assets/style.css"
  >

</head>

<body>

<header>
  <div class="container">

    <a href="/news/">
      ← UniTech LK Technology News
    </a>

  </div>
</header>


<main class="container">

  <div class="hero">

    <span class="label">
      Official Source Monitoring
    </span>

    <h1>
      Windows News &amp; Updates
    </h1>

    <p class="intro">
      Latest Windows announcements and updates discovered
      from official sources. Every UniTech LK news page
      clearly identifies and links to the original publisher.
    </p>

  </div>


  <section>

    <h2>Latest Windows News</h2>

    <div class="guide-grid">

{cards_html}

    </div>

  </section>


  <section class="warning">

    <h2>Source Policy</h2>

    <p>
      UniTech LK does not present third-party announcements
      as its own reporting. News summaries identify the
      original publisher and provide a direct link to the
      original article.
    </p>

  </section>


  <section>

    <h2>Related Topics</h2>

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
          PowerShell
        </a>
      </li>

      <li>
        <a href="/news/">
          All Technology News
        </a>
      </li>

    </ul>

  </section>

</main>


<footer>
  <div class="container">
    © 2026 UniTech LK — Windows news and troubleshooting.
  </div>
</footer>

</body>
</html>
"""

    WINDOWS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    (WINDOWS_DIR / "index.html").write_text(
        index_document,
        encoding="utf-8",
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main() -> int:

    WINDOWS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    state = load_state()

    seen = set(
        state.get("seen", [])
    )

    all_articles = []

    for source in SOURCES:

        try:
            articles = parse_feed(source)

            all_articles.extend(articles)

        except Exception as error:

            log(
                f"Source failed: "
                f"{source['name']}: {error}"
            )

    if not all_articles:

        log(
            "No articles could be retrieved. "
            "Existing site files were left unchanged."
        )

        return 0

    # Remove duplicate URLs.
    unique = {}

    for article in all_articles:
        unique[article["url"]] = article

    all_articles = list(unique.values())

    all_articles.sort(
        key=lambda item: item["published"],
        reverse=True,
    )

    # VERY IMPORTANT:
    # First execution establishes a baseline.
    # It does NOT flood the website with old RSS posts.
    if not state.get("initialized", False):

        log(
            "First run detected. Establishing RSS baseline."
        )

        for article in all_articles:
            seen.add(article["url"])

        state["seen"] = list(seen)
        state["initialized"] = True

        save_state(state)

        update_windows_index()

        log(
            "Baseline complete. No historical articles "
            "were automatically published."
        )

        return 0

    new_articles = [
        article
        for article in all_articles
        if article["url"] not in seen
    ]

    # Oldest first so chronological creation is cleaner.
    new_articles.sort(
        key=lambda item: item["published"]
    )

    new_articles = new_articles[
        :MAX_NEW_ARTICLES_PER_RUN
    ]

    created = 0

    for article in new_articles:

        try:
            slug, status = create_article_page(
                article
            )

            seen.add(article["url"])

            if status == "created":

                created += 1

                log(
                    f"Created: "
                    f"/news/windows/{slug}/"
                )

                log(
                    f"Original source: "
                    f"{article['url']}"
                )

        except Exception as error:

            log(
                f"Could not create article "
                f"{article['title']}: {error}"
            )

    state["seen"] = list(seen)

    save_state(state)

    update_windows_index()

    log(
        f"Finished. New articles created: {created}"
    )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())

    except KeyboardInterrupt:
        sys.exit(130)

    except Exception as error:
        print(
            f"[UniTech LK] Fatal error: {error}",
            file=sys.stderr,
        )
        sys.exit(1)
