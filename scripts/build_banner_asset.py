#!/usr/bin/env python3
"""Restore the approved Articles hero from checksum-verified repository chunks.

This runs in CI before the FTPES mirror. The encoded chunks are versioned in
Git because the connected file API cannot reliably upload larger binary files.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS_DIR = ROOT / "asset_sources" / "articles-banner"
DESTINATION = ROOT / "site" / "assets" / "articles-banner-approved.avif"
EXPECTED_PARTS = 10
EXPECTED_SIZE = 35535
EXPECTED_SHA256 = "e43e96e0d6f54632455dfb8fde48a9ef85d1e6fcfc0121f91f75484f9064b05f"


def main() -> None:
    parts = sorted(PARTS_DIR.glob("part-*.b64"))
    if len(parts) != EXPECTED_PARTS:
        raise SystemExit(f"Expected {EXPECTED_PARTS} banner chunks; found {len(parts)}")
    expected_names = [f"part-{number:02d}.b64" for number in range(1, EXPECTED_PARTS + 1)]
    if [part.name for part in parts] != expected_names:
        raise SystemExit("Banner chunk names or ordering do not match the manifest")
    content = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    image = base64.b64decode(content, validate=True)
    actual_sha256 = hashlib.sha256(image).hexdigest()
    if len(image) != EXPECTED_SIZE or actual_sha256 != EXPECTED_SHA256:
        raise SystemExit(f"Banner checksum/size mismatch: {len(image)} bytes, SHA256={actual_sha256}")
    if image[4:12] != b"ftypavif":
        raise SystemExit("Restored banner is not an AVIF image")

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_bytes(image)

    css_path = ROOT / "site" / "assets" / "articles.css"
    css = css_path.read_text(encoding="utf-8")
    old = 'url("hero-diamond-head.jpg") center 48%/cover no-repeat'
    new = 'url("articles-banner-approved.avif") center 48%/cover no-repeat'
    if css.count(old) != 1:
        raise SystemExit("Articles hero CSS rule changed: refusing to patch an unexpected stylesheet")
    css_path.write_text(css.replace(old, new, 1), encoding="utf-8")

    index_path = ROOT / "site" / "articles" / "index.html"
    index = index_path.read_text(encoding="utf-8")
    old_version = 'articles.css?v=20260913-1'
    new_version = 'articles.css?v=20260920-banner-2'
    if index.count(old_version) != 1:
        raise SystemExit("Articles stylesheet link changed: refusing to patch an unexpected page")
    index_path.write_text(index.replace(old_version, new_version, 1), encoding="utf-8")
    print(f"Restored approved Articles banner: {DESTINATION} ({len(image)} bytes, SHA256={actual_sha256})")


if __name__ == "__main__":
    main()
