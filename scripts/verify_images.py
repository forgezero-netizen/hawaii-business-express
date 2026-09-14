#!/usr/bin/env python3
from __future__ import annotations

import struct
import sys
import time
import zlib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content" / "articles"
BASE_URL = "https://hawaiibusinessexpress.com"
USER_AGENT = "HawaiiBusinessExpress-ImageVerifier/1.0"
RETRIES = 6
RETRY_DELAY_SECONDS = 4
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class VerificationError(RuntimeError):
    pass


def with_cache_bust(url: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["verify_image"] = str(int(time.time()))
    return urlunparse(parsed._replace(query=urlencode(query)))


def fetch_bytes(url: str) -> bytes:
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
                if not data:
                    raise VerificationError(f"{url} returned zero bytes")
                return data
        except (HTTPError, URLError, TimeoutError, VerificationError) as exc:
            last_error = exc
            if attempt < RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
    raise VerificationError(f"Unable to fetch {url}: {last_error}")


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise VerificationError(f"{path}: missing YAML front matter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise VerificationError(f"{path}: malformed YAML front matter")
    return yaml.safe_load(parts[1]) or {}


def validate_png(data: bytes, url: str) -> tuple[int, int]:
    if not data.startswith(PNG_SIGNATURE):
        raise VerificationError(f"{url}: expected PNG signature")

    pos = len(PNG_SIGNATURE)
    width = height = 0
    saw_ihdr = False
    saw_iend = False

    while pos < len(data):
        if pos + 8 > len(data):
            raise VerificationError(f"{url}: truncated PNG chunk header")
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8]
        data_start = pos + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(data):
            name = chunk_type.decode("ascii", errors="replace")
            raise VerificationError(f"{url}: truncated PNG chunk {name}")

        chunk_data = data[data_start:data_end]
        expected_crc = struct.unpack(">I", data[data_end:crc_end])[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            name = chunk_type.decode("ascii", errors="replace")
            raise VerificationError(f"{url}: PNG CRC failure in chunk {name}")

        if chunk_type == b"IHDR":
            if saw_ihdr or length != 13:
                raise VerificationError(f"{url}: invalid PNG IHDR")
            width, height = struct.unpack(">II", chunk_data[:8])
            saw_ihdr = True
        elif chunk_type == b"IEND":
            if length != 0:
                raise VerificationError(f"{url}: invalid PNG IEND")
            saw_iend = True
            if crc_end != len(data):
                raise VerificationError(f"{url}: unexpected trailing bytes after PNG IEND")
            break

        pos = crc_end

    if not saw_ihdr or not saw_iend:
        raise VerificationError(f"{url}: incomplete PNG structure")
    if width < 600 or height < 300:
        raise VerificationError(f"{url}: hero image is only {width}x{height}; expected at least 600x300")
    return width, height


def main() -> int:
    checked = 0
    for path in sorted(CONTENT_DIR.glob("*.md")):
        if path.name in {"ARTICLE-TEMPLATE.md", "README.md"}:
            continue
        meta = parse_frontmatter(path)
        draft = meta.get("draft", True)
        if isinstance(draft, str):
            draft = draft.lower() == "true"
        if draft:
            continue
        image = str(meta.get("image") or "").strip()
        if not image.lower().endswith(".png"):
            continue
        url = image if image.startswith(("http://", "https://")) else f"{BASE_URL}{image}"
        data = fetch_bytes(url)
        width, height = validate_png(data, url)
        print(f"✓ Valid PNG hero: {url} ({width}x{height}, {len(data):,} bytes)")
        checked += 1

    print(f"Hero image binary verification complete: {checked} PNG hero image(s) validated.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as exc:
        print(f"HERO IMAGE VERIFICATION ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
