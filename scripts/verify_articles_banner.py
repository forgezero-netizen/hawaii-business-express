#!/usr/bin/env python3
"""Verify the approved Articles-library banner is actually deployed and referenced."""
from __future__ import annotations

import hashlib
import time
from urllib.request import Request, urlopen

BASE = "https://hawaiibusinessexpress.com"
EXPECTED_SHA256 = "e43e96e0d6f54632455dfb8fde48a9ef85d1e6fcfc0121f91f75484f9064b05f"
IMAGE = "/assets/articles-banner-approved.avif"
CSS = "/assets/articles.css?v=20260920-banner-2"


def fetch(url: str) -> bytes:
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}banner_verify={int(time.time())}"
    last_error = None
    for attempt in range(6):
        try:
            req = Request(url, headers={"User-Agent": "HBE-ArticlesBannerVerifier/1.0", "Cache-Control": "no-cache"})
            with urlopen(req, timeout=25) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status} for {url}")
                return response.read()
        except Exception as error:
            last_error = error
            if attempt < 5:
                time.sleep(4)
    raise RuntimeError(f"Could not retrieve {url}: {last_error}")


def main() -> None:
    html = fetch(BASE + "/articles/").decode("utf-8")
    if 'articles.css?v=20260920-banner-2' not in html:
        raise SystemExit("Live Articles page does not reference the refreshed banner stylesheet")
    css = fetch(BASE + CSS).decode("utf-8")
    if 'url("articles-banner-approved.avif") center 48%/cover no-repeat' not in css:
        raise SystemExit("Live Articles CSS does not reference the approved banner")
    image = fetch(BASE + IMAGE)
    digest = hashlib.sha256(image).hexdigest()
    if len(image) != 35535 or digest != EXPECTED_SHA256 or image[4:12] != b"ftypavif":
        raise SystemExit(f"Live Articles banner is missing, truncated or changed: bytes={len(image)} sha256={digest}")
    print(f"✓ Articles banner verified live: {BASE + IMAGE} ({len(image)} bytes; SHA256 {digest})")
    print("✓ Live Articles page references the cache-busted stylesheet and approved AVIF hero")


if __name__ == "__main__":
    main()
