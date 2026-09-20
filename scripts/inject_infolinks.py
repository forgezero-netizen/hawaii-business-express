#!/usr/bin/env python3
"""Insert the publisher-provided Infolinks tag in built HTML before </body>.

Run after the article build, before FTPES deployment. The source templates remain
unchanged; every deployment re-creates the tags in both static and generated pages.
"""
from pathlib import Path
import re

SITE = Path(__file__).resolve().parents[1] / "site"
TAG = (
    '  <script type="text/javascript"> var infolinks_pid = 3447991; var infolinks_wsid = 0; </script>\n'
    '  <script type="text/javascript" src="//resources.infolinks.com/js/infolinks_main.js"></script>\n'
)
CLOSING_BODY = re.compile(r"</body\s*>", re.IGNORECASE)


def main() -> None:
    pages = sorted(SITE.rglob("*.html"))
    if not pages:
        raise RuntimeError("No HTML pages found for Infolinks integration")
    changed = 0
    for page in pages:
        html = page.read_text(encoding="utf-8")
        if html.count("infolinks_pid") or html.count("infolinks_main.js"):
            # Fail closed on unexpected pre-existing ad tags instead of duplicating them.
            if html.count(TAG) != 1 or html.count("infolinks_pid") != 1 or html.count("infolinks_main.js") != 1:
                raise RuntimeError(f"Conflicting or duplicate Infolinks tag in {page}")
            if not re.search(re.escape(TAG) + r"</body\s*>", html, re.IGNORECASE):
                raise RuntimeError(f"Infolinks tag is not immediately before </body> in {page}")
            continue
        matches = list(CLOSING_BODY.finditer(html))
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one closing body tag in {page}; got {len(matches)}")
        pos = matches[0].start()
        html = html[:pos] + TAG + html[pos:]
        page.write_text(html, encoding="utf-8")
        changed += 1
    print(f"Infolinks publisher 3447991: {changed} HTML page(s) updated, {len(pages)} checked.")


if __name__ == "__main__":
    main()
