import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]

VIDEOS_DIR = ROOT / "data" / "videos"
PREVIEW_DIR = ROOT / "preview-output"

SITE_URL = "https://unitechlk.com"

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class PreviewHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()

        self.meta_tags = []
        self.links = []
        self.h1_count = 0

        self.in_json_ld = False
        self.current_json_ld = []
        self.json_ld_blocks = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag.lower() == "meta":
            self.meta_tags.append(attrs_dict)

        elif tag.lower() == "link":
            self.links.append(attrs_dict)

        elif tag.lower() == "h1":
            self.h1_count += 1

        elif tag.lower() == "script":
            script_type = (
                attrs_dict.get("type", "")
                .strip()
                .lower()
            )

            if script_type == "application/ld+json":
                self.in_json_ld = True
                self.current_json_ld = []

    def handle_data(self, data):
        if self.in_json_ld:
            self.current_json_ld.append(data)

    def handle_endtag(self, tag):
        if (
            tag.lower() == "script"
            and self.in_json_ld
        ):
            content = "".join(
                self.current_json_ld
            ).strip()

            if content:
                self.json_ld_blocks.append(
                    content
                )

            self.in_json_ld = False
            self.current_json_ld = []


def fail(message):
    print(f"ERROR: {message}")
    return False


def load_json(path):
    with path.open(
        "r",
        encoding="utf-8"
    ) as handle:
        return json.load(handle)


def find_metadata_for_slug(slug):
    for path in sorted(
        VIDEOS_DIR.glob("*.json")
    ):
        try:
            data = load_json(path)
        except Exception:
            continue

        if data.get("slug") == slug:
            return path, data

    return None, None


def get_robots_content(parser):
    values = []

    for meta in parser.meta_tags:
        name = (
            meta.get("name", "")
            .strip()
            .lower()
        )

        if name == "robots":
            values.append(
                meta.get("content", "")
                .strip()
                .lower()
            )

    return values


def get_canonical_urls(parser):
    urls = []

    for link in parser.links:
        rel = (
            link.get("rel", "")
            .strip()
            .lower()
        )

        if rel == "canonical":
            href = (
                link.get("href", "")
                .strip()
            )

            if href:
                urls.append(href)

    return urls


def collect_schema_types(value):
    found = set()

    if isinstance(value, dict):
        schema_type = value.get("@type")

        if isinstance(schema_type, str):
            found.add(schema_type)

        elif isinstance(schema_type, list):
            for item in schema_type:
                if isinstance(item, str):
                    found.add(item)

        for child in value.values():
            found.update(
                collect_schema_types(child)
            )

    elif isinstance(value, list):
        for child in value:
            found.update(
                collect_schema_types(child)
            )

    return found


def collect_schema_objects(value):
    objects = []

    if isinstance(value, dict):
        objects.append(value)

        for child in value.values():
            objects.extend(
                collect_schema_objects(child)
            )

    elif isinstance(value, list):
        for child in value:
            objects.extend(
                collect_schema_objects(child)
            )

    return objects


def parse_json_ld(parser, preview_name):
    parsed_blocks = []

    for index, block in enumerate(
        parser.json_ld_blocks,
        start=1
    ):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{preview_name}: invalid JSON-LD "
                f"in block {index}: {exc}"
            )

        parsed_blocks.append(parsed)

    return parsed_blocks


def validate_preview_file(path):
    print()
    print("=" * 70)
    print(
        f"Checking preview: "
        f"{path.relative_to(ROOT)}"
    )
    print("=" * 70)

    try:
        resolved_preview = (
            PREVIEW_DIR.resolve()
        )

        resolved_file = path.resolve()

        resolved_file.relative_to(
            resolved_preview
        )

    except ValueError:
        return fail(
            "Preview file escaped the "
            "preview-output directory."
        )

    slug = path.parent.name

    metadata_path, data = (
        find_metadata_for_slug(slug)
    )

    if data is None:
        return fail(
            f"{path.name}: no metadata JSON "
            f"found for slug '{slug}'."
        )

    print(
        f"Metadata: "
        f"{metadata_path.relative_to(ROOT)}"
    )

    video_id = data.get(
        "video_id",
        ""
    )

    if not isinstance(
        video_id,
        str
    ):
        return fail(
            f"{slug}: video_id must be text."
        )

    if not YOUTUBE_ID_RE.fullmatch(
        video_id
    ):
        return fail(
            f"{slug}: invalid YouTube video ID."
        )

    expected_canonical = (
        f"{SITE_URL}/{slug}/"
    )

    try:
        html_text = path.read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        return fail(
            f"{slug}: cannot read preview: {exc}"
        )

    parser = PreviewHTMLParser()

    try:
        parser.feed(html_text)
    except Exception as exc:
        return fail(
            f"{slug}: HTML parsing failed: {exc}"
        )

    problems = []

    # ---------------------------------------------------------
    # PREVIEW WARNING
    # ---------------------------------------------------------

    required_warning = (
        "PREVIEW ONLY — NOT PRODUCTION"
    )

    if required_warning not in html_text:
        problems.append(
            "Missing PREVIEW ONLY warning."
        )

    # ---------------------------------------------------------
    # ROBOTS PROTECTION
    # ---------------------------------------------------------

    robots_values = (
        get_robots_content(parser)
    )

    if not robots_values:
        problems.append(
            "Missing robots meta tag."
        )
    else:
        safe_robots_found = False

        for robots in robots_values:
            directives = {
                item.strip()
                for item in robots.split(",")
                if item.strip()
            }

            if {
                "noindex",
                "nofollow",
                "noarchive",
            }.issubset(directives):
                safe_robots_found = True

            if (
                "index" in directives
                or "follow" in directives
            ):
                problems.append(
                    "Unsafe robots directive "
                    f"detected: {robots}"
                )

        if not safe_robots_found:
            problems.append(
                "Preview robots tag must contain "
                "noindex,nofollow,noarchive."
            )

    # ---------------------------------------------------------
    # CANONICAL
    # ---------------------------------------------------------

    canonical_urls = (
        get_canonical_urls(parser)
    )

    if len(canonical_urls) != 1:
        problems.append(
            "Preview must contain exactly "
            "one canonical link."
        )

    elif (
        canonical_urls[0]
        != expected_canonical
    ):
        problems.append(
            "Canonical URL mismatch. "
            f"Expected {expected_canonical} "
            f"but found {canonical_urls[0]}"
        )

    # ---------------------------------------------------------
    # H1
    # ---------------------------------------------------------

    if parser.h1_count != 1:
        problems.append(
            "Preview must contain exactly "
            f"one H1. Found {parser.h1_count}."
        )

    # ---------------------------------------------------------
    # YOUTUBE ID
    # ---------------------------------------------------------

    if video_id not in html_text:
        problems.append(
            "Expected YouTube video ID "
            "was not found in preview."
        )

    expected_embed = (
        f"https://www.youtube.com/embed/"
        f"{video_id}"
    )

    if expected_embed not in html_text:
        problems.append(
            "Expected YouTube embed URL "
            "was not found."
        )

    # ---------------------------------------------------------
    # PLACEHOLDERS
    # ---------------------------------------------------------

    forbidden_placeholders = [
        "VIDEO_ID_HERE",
        "VIDEO TITLE HERE",
        "video-page-slug",
        "Short original UniTech LK description",
    ]

    for placeholder in forbidden_placeholders:
        if placeholder in html_text:
            problems.append(
                "Template placeholder detected: "
                f"{placeholder}"
            )

    # ---------------------------------------------------------
    # STRUCTURED DATA
    # ---------------------------------------------------------

    try:
        schemas = parse_json_ld(
            parser,
            path.name
        )
    except ValueError as exc:
        problems.append(str(exc))
        schemas = []

    schema_types = set()
    schema_objects = []

    for schema in schemas:
        schema_types.update(
            collect_schema_types(schema)
        )

        schema_objects.extend(
            collect_schema_objects(schema)
        )

    required_schema_types = {
        "VideoObject",
        "TechArticle",
        "BreadcrumbList",
    }

    missing_schema = (
        required_schema_types
        - schema_types
    )

    if missing_schema:
        problems.append(
            "Missing structured data type(s): "
            + ", ".join(
                sorted(missing_schema)
            )
        )

    # ---------------------------------------------------------
    # VIDEOOBJECT MATCHING
    # ---------------------------------------------------------

    video_objects = [
        item
        for item in schema_objects
        if item.get("@type")
        == "VideoObject"
    ]

    if len(video_objects) != 1:
        problems.append(
            "Preview must contain exactly "
            "one VideoObject."
        )

    else:
        video_object = (
            video_objects[0]
        )

        schema_embed = (
            video_object.get(
                "embedUrl",
                ""
            )
        )

        schema_content = (
            video_object.get(
                "contentUrl",
                ""
            )
        )

        if (
            video_id
            not in str(schema_embed)
        ):
            problems.append(
                "VideoObject embedUrl does not "
                "match metadata video_id."
            )

        if (
            video_id
            not in str(schema_content)
        ):
            problems.append(
                "VideoObject contentUrl does not "
                "match metadata video_id."
            )

        expected_title = (
            data.get(
                "title",
                ""
            )
        )

        if (
            video_object.get("name")
            != expected_title
        ):
            problems.append(
                "VideoObject name does not "
                "match metadata title."
            )

    # ---------------------------------------------------------
    # TECHARTICLE MATCHING
    # ---------------------------------------------------------

    article_objects = [
        item
        for item in schema_objects
        if item.get("@type")
        == "TechArticle"
    ]

    if len(article_objects) != 1:
        problems.append(
            "Preview must contain exactly "
            "one TechArticle."
        )

    else:
        article = (
            article_objects[0]
        )

        if (
            article.get("headline")
            != data.get("title")
        ):
            problems.append(
                "TechArticle headline does not "
                "match metadata title."
            )

    # ---------------------------------------------------------
    # URL SAFETY
    # ---------------------------------------------------------

    parsed_canonical = (
        urlparse(
            expected_canonical
        )
    )

    if (
        parsed_canonical.scheme
        != "https"
    ):
        problems.append(
            "Canonical URL must use HTTPS."
        )

    if (
        parsed_canonical.netloc
        != "unitechlk.com"
    ):
        problems.append(
            "Canonical URL must use "
            "unitechlk.com."
        )

    # ---------------------------------------------------------
    # CLASSIFICATION / PROTECTION
    # ---------------------------------------------------------

    production_file = (
        ROOT /
        slug /
        "index.html"
    )

    if production_file.exists():
        required_protection_text = (
            "EXISTING PRODUCTION CONTENT "
            "— PROTECTED"
        )

        if (
            required_protection_text
            not in html_text
        ):
            problems.append(
                "Existing production page detected "
                "but PROTECTED classification "
                "is missing from preview."
            )

    # ---------------------------------------------------------
    # RESULT
    # ---------------------------------------------------------

    if problems:
        print()
        print("SAFETY CHECK: FAILED")
        print("--------------------")

        for problem in problems:
            print(
                f"- {problem}"
            )

        return False

    print()
    print("SAFETY CHECK: PASS")
    print("------------------")

    print(
        "✓ Preview-only warning present"
    )

    print(
        "✓ noindex/nofollow/noarchive present"
    )

    print(
        "✓ Canonical URL matches metadata"
    )

    print(
        "✓ Exactly one H1"
    )

    print(
        "✓ YouTube video ID matches"
    )

    print(
        "✓ VideoObject valid"
    )

    print(
        "✓ TechArticle valid"
    )

    print(
        "✓ BreadcrumbList present"
    )

    print(
        "✓ No template placeholders detected"
    )

    if production_file.exists():
        print(
            "✓ Existing production page "
            "is marked PROTECTED"
        )

    return True


def main():
    print(
        "UniTech LK Preview Safety Validator"
    )

    print(
        "=================================="
    )

    if not PREVIEW_DIR.exists():
        print(
            "ERROR: preview-output directory "
            "does not exist."
        )
        return 1

    preview_files = sorted(
        PREVIEW_DIR.glob(
            "*/index.html"
        )
    )

    if not preview_files:
        print(
            "ERROR: No generated preview "
            "index.html files found."
        )
        return 1

    print(
        f"Found {len(preview_files)} "
        "preview file(s)."
    )

    all_valid = True

    for path in preview_files:
        if not validate_preview_file(
            path
        ):
            all_valid = False

    print()
    print("=" * 70)

    if all_valid:
        print(
            "SUCCESS: All HTML previews "
            "passed safety validation."
        )

        print(
            "Production website files "
            "remain unchanged."
        )

        return 0

    print(
        "FAILED: One or more HTML previews "
        "did not pass safety validation."
    )

    print(
        "Production publishing must remain blocked."
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())
