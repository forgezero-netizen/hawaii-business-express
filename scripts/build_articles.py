#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import shutil
import sys
from datetime import date, datetime
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

import markdown
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content" / "articles"
SITE_DIR = ROOT / "site"
ARTICLES_DIR = SITE_DIR / "articles"
ASSETS_DIR = SITE_DIR / "assets"
INDEX_PATH = ASSETS_DIR / "articles-index.json"
SITEMAP_PATH = SITE_DIR / "sitemap.xml"

BASE_URL = "https://hawaiibusinessexpress.com"
ALLOWED_CATEGORIES = {
    "Starting a Business",
    "Managing a Business",
    "Compliance",
    "Taxes",
    "Financing",
    "Marketing",
    "Business Strategy",
}
REQUIRED = ("title", "slug", "description", "category", "published")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class BuildError(Exception):
    pass


def fail(message: str) -> None:
    raise BuildError(message)


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        fail(f"{path}: missing YAML front matter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        fail(f"{path}: malformed YAML front matter")
    metadata = yaml.safe_load(parts[1]) or {}
    if not isinstance(metadata, dict):
        fail(f"{path}: front matter must be a mapping")
    return metadata, parts[2].lstrip()


def iso_date(value, field: str, path: Path) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            pass
    fail(f"{path}: {field} must be YYYY-MM-DD")


def as_bool(value, field: str, path: Path) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    fail(f"{path}: {field} must be true or false")


def normalize_image(value, slug: str) -> str:
    if not value:
        return ""
    value = str(value).strip()
    if value.startswith(("https://", "http://", "/")):
        return value
    return f"/assets/articles/{slug}/{value}"


def word_count(markdown_body: str) -> int:
    stripped = re.sub(r"`{1,3}.*?`{1,3}", " ", markdown_body, flags=re.S)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    stripped = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", stripped)
    stripped = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", stripped)
    return len(re.findall(r"\b[\w’ʻ'-]+\b", stripped, flags=re.UNICODE))


def read_time(markdown_body: str) -> str:
    minutes = max(1, math.ceil(word_count(markdown_body) / 220))
    return f"{minutes} min read"


def load_articles() -> list[dict]:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    articles = []
    seen_slugs: set[str] = set()

    for path in sorted(CONTENT_DIR.glob("*.md")):
        if path.name in {"ARTICLE-TEMPLATE.md", "README.md"}:
            continue

        meta, body = parse_frontmatter(path)
        missing = [field for field in REQUIRED if not meta.get(field)]
        if missing:
            fail(f"{path}: missing required field(s): {', '.join(missing)}")

        title = str(meta["title"]).strip()
        slug = str(meta["slug"]).strip()
        description = str(meta["description"]).strip()
        category = str(meta["category"]).strip()

        if not SLUG_RE.fullmatch(slug):
            fail(f"{path}: invalid slug '{slug}'. Use lowercase letters, numbers, and hyphens only.")
        if slug in seen_slugs:
            fail(f"{path}: duplicate slug '{slug}'")
        seen_slugs.add(slug)

        if category not in ALLOWED_CATEGORIES:
            fail(f"{path}: category '{category}' is not approved")

        published = iso_date(meta["published"], "published", path)
        updated = iso_date(meta.get("updated", meta["published"]), "updated", path)
        draft = as_bool(meta.get("draft", True), "draft", path)
        featured = as_bool(meta.get("featured", False), "featured", path)

        keywords = meta.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        if not isinstance(keywords, list):
            fail(f"{path}: keywords must be a YAML list")
        keywords = [str(k).strip() for k in keywords if str(k).strip()]

        author = str(meta.get("author") or "Hawaiʻi Business Express").strip()
        image = normalize_image(meta.get("image", ""), slug)

        articles.append({
            "source": path,
            "title": title,
            "slug": slug,
            "description": description,
            "category": category,
            "keywords": keywords,
            "published": published,
            "updated": updated,
            "featured": featured,
            "draft": draft,
            "author": author,
            "image": image,
            "body": body,
            "readTime": read_time(body),
            "url": f"/articles/{slug}/",
        })

    featured_count = sum(1 for a in articles if not a["draft"] and a["featured"])
    if featured_count > 1:
        fail("Only one published article may have featured: true")
    return articles


def markdown_to_html(body: str) -> str:
    return markdown.markdown(
        body,
        extensions=["extra", "sane_lists", "toc", "smarty"],
        extension_configs={"toc": {"permalink": False}},
        output_format="html5",
    )


def article_page(article: dict, related: list[dict]) -> str:
    canonical = f"{BASE_URL}{article['url']}"
    body_html = markdown_to_html(article["body"])
    title = escape(article["title"])
    description = escape(article["description"])
    category = escape(article["category"])
    author = escape(article["author"])
    image = article["image"]
    og_image = f'\n  <meta property="og:image" content="{escape(BASE_URL + image if image.startswith("/") else image)}">' if image else ""

    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article["title"],
        "description": article["description"],
        "datePublished": article["published"],
        "dateModified": article["updated"],
        "author": {"@type": "Organization", "name": article["author"]},
        "publisher": {"@type": "Organization", "name": "Hawaiʻi Business Express", "url": BASE_URL},
        "mainEntityOfPage": canonical,
    }
    if image:
        schema["image"] = [BASE_URL + image if image.startswith("/") else image]

    related_html = ""
    if related:
        cards = []
        for item in related:
            cards.append(f'''<a class="related-card" href="{escape(item["url"])}"><span class="related-category">{escape(item["category"])}</span><strong>{escape(item["title"])}</strong><span>{escape(item["description"])}</span></a>''')
        related_html = f'''<section class="related-section" aria-labelledby="related-heading"><div class="article-shell"><h2 id="related-heading">Related Articles</h2><div class="related-grid">{''.join(cards)}</div></div></section>'''

    hero_image = f'<img class="article-hero-image" src="{escape(image)}" alt="">' if image else ""
    schema_json = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | Hawaiʻi Business Express</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{canonical}">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/assets/article-page.css?v=20260913-1">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">{og_image}
  <meta property="article:published_time" content="{article["published"]}">
  <meta property="article:modified_time" content="{article["updated"]}">
  <script type="application/ld+json">{schema_json}</script>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-MRNR6J06RW"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','G-MRNR6J06RW');</script>
</head>
<body>
  <a class="skip-link" href="#article">Skip to article</a>
  <header class="site-header"><div class="container header-inner"><a class="brand" href="/index.html" aria-label="Hawaiʻi Business Express home"><img src="/assets/hbe-logo-approved-v4.svg?v=20260913-7" width="590" height="108" alt="Hawaiʻi Business Express — Independent business information service"></a><nav class="site-nav" aria-label="Primary navigation"><a href="/index.html">Home</a><a href="/search.html">Search Businesses</a><a href="/start.html">Start a Business</a><a href="/manage.html">Manage a Business</a><a href="/articles/" aria-current="page">Articles</a><a href="/resources.html">Resources</a></nav></div></header>
  <main id="article"><article><header class="article-header"><div class="article-shell"><p class="article-kicker">{category}</p><h1>{title}</h1><p class="article-deck">{description}</p><div class="article-meta"><span>By {author}</span><span>Published <time datetime="{article["published"]}">{article["published"]}</time></span><span>{escape(article["readTime"])}</span></div>{hero_image}</div></header><div class="article-shell article-layout"><div class="article-body">{body_html}</div><aside class="article-aside" aria-label="Article information"><div class="aside-card"><strong>Business Articles</strong><p>Practical, independent information for Hawaiʻi businesses.</p><a href="/articles/">Search all articles →</a></div><div class="aside-card"><strong>Important</strong><p>Information is general and may change. Verify current legal, tax, filing, licensing, and regulatory requirements with the responsible agency or a qualified professional.</p></div></aside></div></article>{related_html}</main>
  <footer class="site-footer"><div class="container footer-inner"><div class="footer-brand"><img src="/assets/hbe-logo-approved-v4.svg?v=20260913-7" alt="Hawaiʻi Business Express"><p>Independent business information and navigation for Hawaiʻi businesses.</p></div><nav class="footer-links" aria-label="Footer navigation"><a href="/articles/">Articles</a><a href="/resources.html">Resources</a><a href="/about.html">About</a><a href="/contact.html">Contact</a><a href="/privacy.html">Privacy</a><a href="/terms.html">Terms</a></nav></div><div class="container footer-small">© {datetime.now().year} Hawaiʻi Business Express. Not a State of Hawaiʻi government website.</div></footer>
</body>
</html>
'''


def write_index(published: list[dict]) -> None:
    payload = [{
        "title": a["title"], "url": a["url"], "date": a["published"], "updated": a["updated"],
        "category": a["category"], "keywords": a["keywords"], "description": a["description"],
        "featured": a["featured"], "image": a["image"], "readTime": a["readTime"],
    } for a in published]
    INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_sitemap(published: list[dict]) -> None:
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    if SITEMAP_PATH.exists():
        tree = ET.parse(SITEMAP_PATH)
        root = tree.getroot()
    else:
        root = ET.Element("{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")
        tree = ET.ElementTree(root)

    article_prefix = f"{BASE_URL}/articles/"
    for node in list(root.findall("sm:url", ns)):
        loc = node.find("sm:loc", ns)
        if loc is not None and loc.text and loc.text.startswith(article_prefix) and loc.text != article_prefix:
            root.remove(node)

    existing = {node.find("sm:loc", ns).text for node in root.findall("sm:url", ns) if node.find("sm:loc", ns) is not None}
    if article_prefix not in existing:
        url = ET.SubElement(root, "{http://www.sitemaps.org/schemas/sitemap/0.9}url")
        ET.SubElement(url, "{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text = article_prefix

    for article in published:
        url = ET.SubElement(root, "{http://www.sitemaps.org/schemas/sitemap/0.9}url")
        ET.SubElement(url, "{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text = f"{BASE_URL}{article['url']}"
        ET.SubElement(url, "{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod").text = article["updated"]

    ET.indent(tree, space="  ")
    tree.write(SITEMAP_PATH, encoding="utf-8", xml_declaration=True)


def clean_generated_article_dirs(published_slugs: set[str]) -> None:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    for child in ARTICLES_DIR.iterdir():
        if child.is_dir() and (child / ".generated-by-articles-build").exists() and child.name not in published_slugs:
            shutil.rmtree(child)


def build() -> None:
    articles = load_articles()
    published = sorted((a for a in articles if not a["draft"]), key=lambda a: (a["published"], a["title"]), reverse=True)
    clean_generated_article_dirs({a["slug"] for a in published})

    for article in published:
        out_dir = ARTICLES_DIR / article["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        related = [other for other in published if other["slug"] != article["slug"] and other["category"] == article["category"]][:3]
        (out_dir / "index.html").write_text(article_page(article, related), encoding="utf-8")
        (out_dir / ".generated-by-articles-build").write_text("managed\n", encoding="utf-8")

    write_index(published)
    update_sitemap(published)
    print(f"Article build complete: {len(published)} published, {len(articles) - len(published)} draft.")


if __name__ == "__main__":
    try:
        build()
    except BuildError as exc:
        print(f"ARTICLE BUILD ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
