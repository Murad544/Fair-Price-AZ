"""Collect a bounded batch, persisting each result and the remaining queue."""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

from .parser import CategoryChanged, ListingUnavailable, parse_detail
from .tap_az import Client


def open_database(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            listing_id TEXT PRIMARY KEY, path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', payload TEXT
        );
        CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    return db


def collect(db, client, limit, max_pages):
    client.check_robots()
    saved = unavailable = out_of_scope = pages = 0
    reason = "limit"
    while saved + unavailable + out_of_scope < limit:
        pending = db.execute("SELECT listing_id, path FROM listings WHERE status='pending' ORDER BY rowid LIMIT 1").fetchone()
        if pending:
            listing_id, path = pending
            try:
                row = parse_detail(client.request(path), listing_id)
            except CategoryChanged as error:
                with db:
                    db.execute("UPDATE listings SET status='out_of_scope' WHERE listing_id=?", (listing_id,))
                out_of_scope += 1
                print(f"Skipped: {error}", flush=True)
                continue
            except ListingUnavailable:
                with db:
                    db.execute("UPDATE listings SET status='unavailable' WHERE listing_id=?", (listing_id,))
                unavailable += 1
                continue
            except HTTPError as error:
                error.close()
                if error.code not in (404, 410):
                    raise
                with db:
                    db.execute("UPDATE listings SET status='unavailable' WHERE listing_id=?", (listing_id,))
                unavailable += 1
                continue
            with db:
                db.execute("UPDATE listings SET status='done', payload=? WHERE listing_id=?",
                           (json.dumps(row, ensure_ascii=False), listing_id))
            saved += 1
            print(f"Saved {saved}/{limit}: {listing_id}", flush=True)
            continue
        state = dict(db.execute("SELECT key, value FROM state"))
        if state.get("exhausted") == "true":
            reason = "end_of_results"
            break
        if pages >= max_pages:
            reason = "page_limit"
            break
        nodes, cursor, has_next = client.page(state.get("cursor"))
        paths = []
        for node in nodes:
            path = node.get("path", "")
            match = re.fullmatch(r"/elanlar/elektronika/telefonlar/(\d+)", path)
            if not match:
                raise ValueError(f"Unexpected listing path: {path}")
            paths.append((match[1], path))
        if not paths and has_next:
            raise ValueError("Empty batch claims more results; inspect pagination")
        # Queue and cursor move together, so a crash never skips unsaved listings.
        with db:
            db.executemany("INSERT OR IGNORE INTO listings(listing_id,path) VALUES (?,?)", paths)
            db.execute("INSERT OR REPLACE INTO state VALUES ('cursor', ?)", (cursor or "",))
            db.execute("INSERT OR REPLACE INTO state VALUES ('exhausted', ?)", (json.dumps(not has_next),))
        pages += 1
    return {"saved_this_run": saved, "unavailable_this_run": unavailable,
            "out_of_scope_this_run": out_of_scope,
            "pages_fetched": pages, "stop_reason": reason}


def export_and_report(db, output):
    rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM listings WHERE status='done' ORDER BY rowid")]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(output)
    fields = ("price_azn", "brand", "model", "storage_gb", "ram_gb", "condition", "description")
    return {
        "total_saved": len(rows),
        "queue": dict(db.execute("SELECT status, COUNT(*) FROM listings GROUP BY status")),
        "missing": {field: sum(r.get(field) in (None, "") for r in rows) for field in fields},
        "needs_category_review": sum(not r.get("brand") or not r.get("model") for r in rows),
        "note": "Unfiltered category candidates; missing brand/model is a review signal, not a phone classifier.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=30, help="Maximum detail attempts this run")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum new index batches this run")
    parser.add_argument("--delay", type=float, default=3)
    parser.add_argument("--user-agent", default="FairPriceAZ/0.2 (research prototype)")
    parser.add_argument("--db", type=Path, default=Path("data/raw/listings.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("data/raw/listings.jsonl"))
    args = parser.parse_args()
    if args.limit < 1 or args.max_pages < 1 or args.delay < 3:
        parser.error("limit/max-pages must be positive and delay at least 3 seconds")
    if args.db.resolve() == args.output.resolve():
        parser.error("Database and export must be different files")
    db = open_database(args.db)
    result = {}
    failed = False
    try:
        result = collect(db, Client(args.user_agent, args.delay), args.limit, args.max_pages)
    except (HTTPError, URLError, ValueError, KeyError, TimeoutError) as error:
        failed = True
        result = {"stop_reason": "error", "error": str(error)}
        print(f"Stopped; progress is saved: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        failed = True
        result = {"stop_reason": "interrupted"}
    finally:
        try:
            result.update(export_and_report(db, args.output))
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
