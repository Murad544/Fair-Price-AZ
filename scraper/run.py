"""Parse a saved page: python3 -m scraper.run page.html --output sample.jsonl."""

import argparse
import json
from pathlib import Path

from .parser import parse_detail, parse_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--listing-id", help="Parse one detail page instead of an index")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    html = args.html.read_text(encoding="utf-8")
    rows = [parse_detail(html, args.listing_id)] if args.listing_id else parse_index(html)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids silently replacing an earlier collection.
    with args.output.open("x", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Saved {len(rows)} records to {args.output}")


if __name__ == "__main__":
    main()
