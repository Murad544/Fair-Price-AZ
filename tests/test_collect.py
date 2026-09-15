import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scraper.collect import collect, export_and_report, open_database
from scraper.tap_az import Client
from test_parser import ad, page


class FakeClient:
    def check_robots(self):
        pass

    def page(self, cursor=None):
        ids = [123, 456] if cursor is None else [456, 789]
        return [{"path": ad(i)["path"]} for i in ids], "next" if cursor is None else "last", cursor is None

    def request(self, path):
        return page([ad(int(path.rsplit("/", 1)[1]))])


class CollectionTests(unittest.TestCase):
    def test_moved_listing_skipped_and_attempt_limit_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            db = open_database(Path(directory) / "test.db")
            moved = ad()
            moved.update(path="/elanlar/elektronika/audio-video/123", legacyResourceId=123)
            client = FakeClient()
            with patch.object(client, "request", return_value=page([moved])) as request:
                result = collect(db, client, 1, 1)
                self.assertEqual(request.call_count, 1)
            self.assertEqual(result["out_of_scope_this_run"], 1)
            self.assertEqual(dict(db.execute("SELECT listing_id,status FROM listings")),
                             {"123": "out_of_scope", "456": "pending"})
            self.assertEqual(collect(db, client, 1, 1)["saved_this_run"], 1)
            db.close()

    def test_resume_queue_pagination_and_dedup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.sqlite3"
            db = open_database(path)
            collect(db, FakeClient(), 1, 2)
            db.close()
            db = open_database(path)
            result = collect(db, FakeClient(), 10, 2)
            self.assertEqual(result["saved_this_run"], 2)
            self.assertEqual(result["stop_reason"], "end_of_results")
            report = export_and_report(db, Path(directory) / "out.jsonl")
            self.assertEqual(report["total_saved"], 3)
            self.assertEqual(report["queue"], {"done": 3})
            db.close()

    def test_block_keeps_pending_for_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            db = open_database(Path(directory) / "test.db")
            client = FakeClient()
            with patch.object(client, "request", side_effect=HTTPError("url", 429, "rate limited", {}, None)):
                with self.assertRaises(HTTPError):
                    collect(db, client, 2, 1)
            self.assertEqual(db.execute("SELECT count(*) FROM listings WHERE status='pending'").fetchone()[0], 2)
            db.close()

    def test_gone_listing_does_not_block_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            db = open_database(Path(directory) / "test.db")
            client = FakeClient()
            with patch.object(client, "request", side_effect=[HTTPError("url", 404, "gone", {}, None), page([ad(456)])]):
                result = collect(db, client, 2, 1)
            self.assertEqual(result["unavailable_this_run"], 1)
            self.assertEqual(result["saved_this_run"], 1)
            db.close()

    def test_soft_missing_listing_does_not_block_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            db = open_database(Path(directory) / "test.db")
            client = FakeClient()
            missing = page([], hasInitialMissingAd=True, adDetails=None)
            with patch.object(client, "request", side_effect=[missing, page([ad(456)])]):
                result = collect(db, client, 2, 1)
            self.assertEqual(result["unavailable_this_run"], 1)
            self.assertEqual(result["saved_this_run"], 1)
            self.assertEqual(dict(db.execute("SELECT listing_id,status FROM listings")),
                             {"123": "unavailable", "456": "done"})
            db.close()

    def test_stuck_cursor_rejected(self):
        client = Client()
        response = {"data": {"adSearch": {"ads": {"nodes": [], "pageInfo": {"endCursor": "same", "hasNextPage": True}}}}}
        with patch.object(client, "request", return_value=json.dumps(response)):
            with self.assertRaises(ValueError):
                client.page("same")

    def test_robots_disallow_prevents_request(self):
        client = Client()
        with patch.object(client, "request", return_value="User-agent: *\nDisallow: /graphql\nCrawl-delay: 5"):
            client.check_robots()
        self.assertEqual(client.delay, 5)
        with patch.object(client.opener, "open") as request:
            with self.assertRaises(ValueError):
                client.request("/graphql", {})
            request.assert_not_called()

    def test_parse_failure_preserves_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            db = open_database(Path(directory) / "test.db")
            client = FakeClient()
            with patch.object(client, "request", return_value="<html>challenge</html>"):
                with self.assertRaises(ValueError):
                    collect(db, client, 2, 1)
            self.assertEqual(db.execute("SELECT count(*) FROM listings WHERE status='pending'").fetchone()[0], 2)
            db.close()

    def test_rate_limit_delay(self):
        client = Client()
        client.last_request = 10
        with patch("scraper.tap_az.time.monotonic", return_value=11), patch("scraper.tap_az.time.sleep") as sleep, patch.object(client.opener, "open") as request:
            request.return_value.__enter__.return_value.read.return_value = b"ok"
            self.assertEqual(client.request("/robots.txt"), "ok")
            sleep.assert_called_once_with(2)
