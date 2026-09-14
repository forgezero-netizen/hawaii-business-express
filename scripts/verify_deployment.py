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
USER_AGENT = "HawaiiBusinessExpress-DeployVerifier/1.1"
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


def date_text(value: object) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).strip()


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
        published = date_text(meta.get("published", ""))
        updated = date_text(meta.get("updated", meta.get("published", "")))
        articles.append({
            "title": str(meta.get("title", "")).strip(),
            "slug": slug,
            "description": str(meta.get("description", "")).strip(),
            "category": str(meta.get("category", "")).strip(),
            "keywords": [str(k).strip() for k in (meta.get("keywords") or [])],
            "image": normalize_image(meta.get("image", ""), slug),
            "published": published,
            "updated": updated,
            "url": f"/articles/{slug}/",
        })
    return articles


def require(fragment: str, page: str, message: str) -> None:
    if fragment not in page:
        raise VerificationError(message)


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


def verify_schema(article: dict, page: str, public_url: str, image_url: str) -> None:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, flags=re.S)
    if not match:
        raise VerificationError(f"{article['slug']}: Article structured data is missing")
    try:
        schema = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{article['slug']}: Article structured data is invalid JSON: {exc}") from exc

    expected = {
        "@type": "Article",
        "headline": article["title"],
        "description": article["description"],
        "datePublished": article["published"],
        "dateModified": article["updated"],
        "mainEntityOfPage": public_url,
    }
    for field, value in expected.items():
        if schema.get(field) != value:
            raise VerificationError(f"{article['slug']}: structured-data field {field!r} is incorrect")

    if image_url:
        images = schema.get("image", [])
        if isinstance(images, str):
            images = [images]
        if image_url not in images:
            raise VerificationError(f"{article['slug']}: structured-data image is missing or incorrect")


def verify_article(article: dict, all_articles: list[dict], index: list[dict], sitemap: str) -> None:
    slug = article["slug"]
    public_url = f"{BASE_URL}{article['url']}"
    page = fetch(public_url)

    title = html.escape(article["title"])
    description = html.escape(article["description"], quote=True)
    image = article["image"]
    image_url = image if image.startswith("http") else (f"{BASE_URL}{image}" if image else "")

    require(f'<link rel="canonical" href="{public_url}">', page, f"{slug}: canonical URL missing or incorrect")
    require(title, page, f"{slug}: title not found in generated article page")
    require(f'<meta name="description" content="{description}">', page, f"{slug}: meta description missing or incorrect")
    require('<meta property="og:type" content="article">', page, f"{slug}: Open Graph type missing or incorrect")
    require(f'<meta property="og:title" content="{title}">', page, f"{slug}: Open Graph title missing or incorrect")
    require(f'<meta property="og:description" content="{description}">', page, f"{slug}: Open Graph description missing or incorrect")
    require(f'<meta property="og:url" content="{public_url}">', page, f"{slug}: Open Graph URL missing or incorrect")
    require(f'<meta property="article:published_time" content="{article["published"]}">', page, f"{slug}: published date metadata missing or incorrect")
    require(f'<meta property="article:modified_time" content="{article["updated"]}">', page, f"{slug}: modified date metadata missing or incorrect")

    if image:
        require(f'src="{html.escape(image)}"', page, f"{slug}: article page does not reference expected hero image {image}")
        require(f'<meta property="og:image" content="{html.escape(image_url, quote=True)}">', page, f"{slug}: Open Graph image missing or incorrect")
        image_bytes = fetch(image_url, binary=True)
        print(f"  ✓ Hero image reachable: {image_url} ({len(image_bytes):,} bytes)")
        if image.lower().endswith(".svg"):
            verify_svg_sidecars(image_url, image_bytes.decode("utf-8", errors="replace"))

    verify_schema(article, page, public_url, image_url)

    matches = [item for item in index if item.get("url") == article["url"]]
    if len(matches) != 1:
        raise VerificationError(f"{slug}: expected exactly one article-index entry, found {len(matches)}")
    item = matches[0]
    for field in ("title", "category", "description", "image"):
        if item.get(field, "") != article[field]:
            raise VerificationError(f"{slug}: article-index field {field!r} does not match source metadata")
    if str(item.get("date", "")) != article["published"]:
        raise VerificationError(f"{slug}: article-index publication date does not match source metadata")
    if str(item.get("updated", "")) != article["updated"]:
        raise VerificationError(f"{slug}: article-index updated date does not match source metadata")

    indexed_keywords = [str(k).strip() for k in item.get("keywords", [])]
    if indexed_keywords != article["keywords"]:
        raise VerificationError(f"{slug}: article-index keywords do not match source metadata")

    title_words = [w.lower() for w in re.findall(r"[A-Za-z0-9ʻ’'-]+", article["title"]) if len(w) >= 3]
    title_query = " ".join(title_words[:2]) if len(title_words) >= 2 else (title_words[0] if title_words else "")
    searchable = " ".join([item.get("title", ""), item.get("description", ""), " ".join(indexed_keywords)]).lower()
    if title_query and title_query not in searchable:
        raise VerificationError(f"{slug}: meaningful title phrase is not discoverable in search metadata")
    if article["keywords"] and article["keywords"][0].lower() not in searchable:
        raise VerificationError(f"{slug}: keyword is not discoverable in search metadata")

    expected_category_count = sum(1 for candidate in all_articles if candidate["category"] == article["category"])
    deployed_category_count = sum(1 for candidate in index if candidate.get("category") == article["category"])
    if deployed_category_count != expected_category_count:
        raise VerificationError(
            f"{slug}: category count mismatch for {article['category']!r}; "
            f"expected {expected_category_count}, deployed index has {deployed_category_count}"
        )

    if public_url not in sitemap:
        raise VerificationError(f"{slug}: URL missing from deployed sitemap")

    print(
        f"✓ {slug}: live page, canonical, Open Graph, Article schema, dates, "
        f"search metadata, category count, sitemap, and image references verified"
    )


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
        verify_article(article, articles, index, sitemap)

    print(f"Deployment verification complete: {len(articles)} published article(s) verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as exc:
        print(f"DEPLOYMENT VERIFICATION ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
