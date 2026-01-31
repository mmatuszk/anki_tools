#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None


def fetch_html(url: str) -> str:
    try:
        import requests  # type: ignore

        headers = {"User-Agent": "Mozilla/5.0 (compatible; anki_tools/1.0)"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception:
        from urllib.request import urlopen
        from urllib.request import Request

        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; anki_tools/1.0)"})
        with urlopen(req, timeout=30) as f:  # nosec - URL provided by user
            return f.read().decode("utf-8", errors="replace")


def extract_simplified(html: str) -> list[str]:
    if BeautifulSoup is None:
        raise RuntimeError("Missing dependency: beautifulsoup4 (bs4). Install with: pip install beautifulsoup4")

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    for table in tables:
        header_idx = None
        for tr in table.find_all("tr"):
            ths = tr.find_all("th")
            if not ths:
                continue
            headers = [th.get_text(" ", strip=True) for th in ths]
            if "Simplified" in headers:
                header_idx = headers.index("Simplified")
                break

        if header_idx is None:
            continue

        simplified = []
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds or len(tds) <= header_idx:
                continue
            text = tds[header_idx].get_text("", strip=True)
            if text:
                simplified.append(text)
        if simplified:
            return simplified

    raise RuntimeError("Could not find a table with a 'Simplified' header.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape the 'Simplified' column from a Wiktionary frequency list.")
    p.add_argument("--url", required=True, help="Source URL to scrape")
    default_dir = Path.home() / "Documents"
    p.add_argument("--dir", dest="out_dir", default=str(default_dir), help="Output directory (default: ~/Documents)")
    p.add_argument("--no-header", action="store_true", default=True, help="Do not write a header row (default: on)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    url = args.url
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    base = url.rstrip("/").split("/")[-1]
    if not base:
        raise RuntimeError("Could not derive output file name from URL.")
    out_path = out_dir / f"{base}.csv"

    html = fetch_html(url)
    simplified = extract_simplified(html)

    # Use UTF-8 with BOM to improve compatibility with Excel/Anki on Windows.
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not args.no_header:
            writer.writerow(["Simplified"])
        for item in simplified:
            writer.writerow([item])

    print(f"Wrote {len(simplified)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1)
