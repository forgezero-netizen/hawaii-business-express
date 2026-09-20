#!/usr/bin/env python3
"""Verify the Infolinks integration is present exactly once on each live page."""
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://hawaiibusinessexpress.com"
SITEMAP = BASE + "/sitemap.xml"
EXPECTED = re.compile(
    r'<script type="text/javascript">\s*var infolinks_pid = 3447991;\s*'
    r'var infolinks_wsid = 0;\s*</script>\s*'
    r'<script type="text/javascript" src="//resources\.infolinks\.com/js/infolinks_main\.js">'
    r'</script>\s*</body\s*>',
    re.IGNORECASE,
)


def get(url: str) -> bytes:
    last = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "HBE-Infolinks-Deploy-Validator/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                return response.read()
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(2)
    raise RuntimeError(f"Unable to retrieve {url}: {last}")


def main() -> None:
    root = ET.fromstring(get(SITEMAP))
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    pages = [node.text for node in root.findall("sm:url/sm:loc", namespace) if node.text]
    if len(pages) < 5 or BASE + "/" not in pages or BASE + "/articles/" not in pages:
        raise RuntimeError("Production sitemap missing expected site pages")
    for url in pages:
        if not (url == BASE + "/" or url.startswith(BASE + "/")):
            raise RuntimeError(f"Unexpected sitemap URL: {url}")
        html = get(url).decode("utf-8")
        if html.count("infolinks_pid") != 1 or html.count("infolinks_main.js") != 1:
            raise RuntimeError(f"Missing or duplicate Infolinks script: {url}")
        if not EXPECTED.search(html):
            raise RuntimeError(f"Infolinks script is not directly before </body>: {url}")
        print(f"✓ Infolinks tag verified: {url}")
    print(f"Infolinks live verification complete: {len(pages)} public page(s) verified.")


if __name__ == "__main__":
    main()
