"""Fetch openly-licensed real package photos from Wikimedia Commons.

Searches several product-type queries (supermarket shelf shots, cartons,
bottles, cans, pouches, blister packs), downloads qualifying JPEG/PNGs into
ml/data/real/raw/ and records attribution in ml/data/real/CREDITS.md.

All Commons files are free-licensed by policy; licenses and artists are
recorded per file so the dataset can be redistributed with attribution.

Usage (inside the backend container):
    python ml/training/fetch_real_photos.py --per-query 30 --max 110
"""

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
from pathlib import Path

import requests

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "DocketSIH26034-ml-training/1.0 (educational hackathon project)"}

QUERIES = [
    "supermarket shelf packaged products",
    "packaged food product packaging",
    "product carton packaging box",
    "shampoo bottle product",
    "milk carton package",
    "cereal box package",
    "medicine blister pack box",
    "cosmetics product packaging",
    "juice bottle label",
    "tin can food product",
]

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "real"
RAW_DIR = OUT_DIR / "raw"


def api_search(query: str, limit: int) -> list[dict]:
    """Search Commons files, returning imageinfo with URL + license metadata."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6,  # File namespace
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|size|sha1|extmetadata",
        "iiurlwidth": 1400,
    }
    resp = requests.get(API, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", {})
    return list(pages.values())


def pick_resolution(info: dict) -> tuple[str, int, int]:
    """Prefer the 1400px thumb (smaller download); fall back to full URL."""
    thumb = info.get("thumburl")
    if thumb:
        return thumb, info.get("thumbwidth", 0), info.get("thumbheight", 0)
    return info["url"], info.get("width", 0), info.get("height", 0)


def download(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        data = resp.content
        if len(data) < 30_000:  # icons/thumbnails
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"  ! download failed: {e}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch real package photos from Commons")
    parser.add_argument("--per-query", type=int, default=30)
    parser.add_argument("--max", type=int, default=110)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Append-safe: continue numbering after existing files and merge prior
    # manifest/credits so re-runs never overwrite or lose attribution.
    import json as _json
    manifest_path = OUT_DIR / "manifest.json"
    manifest: list[dict] = []
    if manifest_path.is_file():
        try:
            manifest = _json.loads(manifest_path.read_text())
        except Exception:
            manifest = []
    seen_sha = {m["sha1"] for m in manifest}
    seen_titles = {m["title"] for m in manifest}
    existing_names = {m["file"] for m in manifest}
    existing_names.update(p.name for p in RAW_DIR.iterdir() if p.is_file())
    counter = 0
    while f"real_{counter:04d}.jpg" in existing_names or f"real_{counter:04d}.png" in existing_names:
        counter += 1

    for qi, query in enumerate(QUERIES):
        print(f"[{qi + 1}/{len(QUERIES)}] {query}")
        try:
            results = api_search(query, args.per_query)
        except Exception as e:
            print(f"  ! search failed: {e}", file=sys.stderr)
            continue

        added_this_query = 0
        for page in results:
            if counter >= args.max:
                break
            title = page.get("title", "")
            if title in seen_titles:
                continue
            info = (page.get("imageinfo") or [{}])[0]
            sha = info.get("sha1", "")
            if not sha or sha in seen_sha:
                continue

            width, height = info.get("width", 0), info.get("height", 0)
            if width < 640 or height < 420:  # too small to be useful
                continue
            if width / max(height, 1) > 3 or height / max(width, 1) > 3:
                continue

            url, tw, th = pick_resolution(info)
            ext = ".png" if url.lower().endswith(".png") else ".jpg"
            fname = f"real_{counter:04d}{ext}"
            while fname in existing_names:  # never overwrite an existing photo
                counter += 1
                fname = f"real_{counter:04d}{ext}"
            dest = RAW_DIR / fname
            if not download(url, dest):
                continue

            meta = info.get("extmetadata", {}) or {}
            def mv(key: str) -> str:
                return (meta.get(key, {}) or {}).get("value", "unknown")

            manifest.append({
                "file": fname,
                "title": title,
                "query": query,
                "source_url": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                "license": mv("LicenseShortName"),
                "artist": mv("Artist"),
                "sha1": sha,
                "downloaded_url": url,
            })
            seen_sha.add(sha)
            seen_titles.add(title)
            counter += 1
            added_this_query += 1
            time.sleep(0.15)  # polite rate limit
        print(f"  +{added_this_query} (total {counter})")
        if counter >= args.max:
            break

    # Write credits + manifest (merged with any prior content)
    manifest.extend([])  # no-op; new entries already appended below
    credits_path = OUT_DIR / "CREDITS.md"
    prior_lines: list[str] = []
    if credits_path.is_file():
        for line in credits_path.read_text().splitlines():
            if line.startswith("- **"):
                prior_lines.append(line)
    credits = ["# Real Photo Credits (Wikimedia Commons)", "",
               "All photos fetched from Wikimedia Commons under their respective free licenses.",
               "Attribution for each file below.", ""]
    credits.extend(prior_lines)
    for m in manifest:
        entry = f"- **{m['file']}** — {m['title']} — {m['license']} — {m['artist']} — {m['source_url']}"
        if entry not in prior_lines:
            credits.append(entry)
    credits_path.write_text("\n".join(credits) + "\n")
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nFetched {len(manifest)} photos total -> {RAW_DIR}")
    print(f"Credits -> {credits_path}")


if __name__ == "__main__":
    main()
