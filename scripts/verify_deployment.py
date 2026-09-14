#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content" / "articles"
BASE_URL = "https://hawaiibusinessexpress.com"
USER_AGENT = "HawaiiBusinessExpress-DeployVerifier/1.0"
RETRIES = 6
RETRY_DELAY_SECONDS = 4


class VerificationError(RuntimeError):
    pass


def with_cache_bust(url: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["verify"] = str(int(time.time()))
    return urlunparse(parsed._replace(query=urlencode(query)))


def fetch(url: str, *, binary: bool = False) -> bytes | str:
    last_error: Exception | None = None
    target = with_cache_bust(url)
    for attempt in range(1, RETRIES + 1):
        try:
            req = Request(target, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
            with urlopen(req, timeout=25) as response:
                status = getattr(response, "status", 200)
                if status < 200 or status >= 400:
                    raise VerificationError(f"{url} returned HTTP {status}")
                data = response.read()
                return data if binary else data.decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, VerificationError) as exc:
            last_error = exc
            if attempt < RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
    raise VerificationError(f"Unable to fetch {url}: {last_error}")


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise VerificationError(f"{path}: missing YAML front matter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise VerificationError(f"{path}: malformed YAML front matter")
    return yaml.safe_load(parts[1]) or {}, parts[2].lstrip()


def normalize_image(value: object, slug: str) -> str:
    if not value:
        return ""
    image = str(value).strip()
    if image.startswith(("https://", "http://", "/")):
        return image
    return f"/assets/articles/{slug}/{image}"


def load_published_articles() -> list[dict]:
    articles: list[dict] = []
    for path in sorted(CONTENT_DIR.glob("*.md")):
        if path.name in {"ARTICLE-TEMPLATE.md", "README.md"}:
            continue
        meta, _ = parse_frontmatter(path)
        draft = meta.get("draft", True)
        if isinstance(draft, str):
            draft = draft.lower() == "true"
        if draft:
            continue
        slug = str(meta.get("slug", "")).strip()
        if not slug:
            raise VerificationError(f"{path}: missing slug")
        articles.append({
            "title": str(meta.get("title", "")).strip(),
            "slug": slug,
            "description": str(meta.get("description", "")).strip(),
            "category": str(meta.get("category", "")).strip(),
            "keywords": [str(k).strip() for k in (meta.get("keywords") or [])],
            "image": normalize_image(meta.get("image", ""), slug),
            "url": f"/articles/{slug}/",
        })
    return articles


def verify_svg_sidecars(image_url: str, svg_text: str) -> None:
    refs = []
    for match in re.finditer(r"(?:href|xlink:href)=[\"']([^\"']+)[\"']", svg_text):
        ref = match.group(1).strip()
        if not ref or ref.startswith(("#", "data:")):
            continue
        refs.append(ref)
    for ref in sorted(set(refs)):
        sidecar_url = urljoin(image_url, ref)
        fetch(sidecar_url, binary=True)
        print(f"  ✓ SVG sidecar reachable: {sidecar_url}")


def verify_article(article: dict, index: list[dict], sitemap: str) -> None:
    slug = article["slug"]
    public_url = f"{BASE_URL}{article['url']}"
    page = fetch(public_url)

    canonical = f'<link rel="canonical" href="{public_url}">'
    if canonical not in page:
        raise VerificationError(f"{slug}: canonical URL missing or incorrect")

    title = html.escape(article["title"])
    if title not in page:
        raise VerificationError(f"{slug}: title not found in generated article page")

    image = article["image"]
    if image:
        if f'src="{html.escape(image)}"' not in page:
            raise VerificationError(f"{slug}: article page does not reference expected hero image {image}")
        image_url = image if image.startswith("http") else f"{BASE_URL}{image}"
        image_bytes = fetch(image_url, binary=True)
        print(f"  ✓ Hero image reachable: {image_url} ({len(image_bytes):,} bytes)")
        if image.lower().endswith(".svg"):
            verify_svg_sidecars(image_url, image_bytes.decode("utf-8", errors="replace"))

    matches = [item for item in index if item.get("url") == article["url"]]
    if len(matches) != 1:
        raise VerificationError(f"{slug}: expected exactly one article-index entry, found {len(matches)}")
    item = matches[0]
    for field in ("title", "category", "description", "image"):
        if item.get(field, "") != article[field]:
            raise VerificationError(f"{slug}: article-index field {field!r} does not match source metadata")

    indexed_keywords = [str(k) for k in item.get("keywords", [])]
    if article["keywords"] and not indexed_keywords:
        raise VerificationError(f"{slug}: keywords missing from article index")
    if not item.get("title"):
        raise VerificationError(f"{slug}: title missing from article index")

    if public_url not in sitemap:
        raise VerificationError(f"{slug}: URL missing from deployed sitemap")

    print(f"✓ {slug}: article page, metadata, search index, category, sitemap, and image references verified")


def main() -> int:
    articles = load_published_articles()
    if not articles:
        raise VerificationError("No published articles found to verify")

    library_page = fetch(f"{BASE_URL}/articles/")
    if "data-article-results" not in library_page:
        raise VerificationError("Articles library page is not serving the expected article-library markup")

    index_text = fetch(f"{BASE_URL}/assets/articles-index.json")
    try:
        index = json.loads(index_text)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"Deployed article index is not valid JSON: {exc}") from exc
    if not isinstance(index, list):
        raise VerificationError("Deployed article index must be a JSON array")

    sitemap = fetch(f"{BASE_URL}/sitemap.xml")

    for article in articles:
        verify_article(article, index, sitemap)

    print(f"Deployment verification complete: {len(articles)} published article(s) verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as exc:
        print(f"DEPLOYMENT VERIFICATION ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
