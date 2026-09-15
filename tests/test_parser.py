import json
import unittest

from scraper.parser import CategoryChanged, ListingUnavailable, parse_detail, parse_index


def page(ads, **page_props):
    page_props["apolloState"] = {str(i): a for i, a in enumerate(ads)}
    payload = {"props": {"pageProps": page_props}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(payload) + '</script>'


def ad(number=123):
    return {"__typename": "Ad", "path": f"/elanlar/elektronika/telefonlar/{number}",
            "price": 555, "body": "sample", "properties": [
                {"name": "Yaddaş", "value": "256GB/6GB"},
                {"name": "Yeni?", "value": "Xeyr"}]}


class ParserTests(unittest.TestCase):
    def test_category_change_requires_matching_identity(self):
        moved = ad()
        moved.update(path="/elanlar/elektronika/audio-video/123", legacyResourceId=123)
        with self.assertRaises(CategoryChanged):
            parse_detail(page([moved]), "123")
        moved["legacyResourceId"] = 456
        with self.assertRaises(ValueError) as error:
            parse_detail(page([moved]), "123")
        self.assertNotIsInstance(error.exception, CategoryChanged)

    def test_memory_condition_and_unknowns(self):
        row = parse_detail(page([ad()]), "123")
        self.assertEqual((row["storage_gb"], row["ram_gb"], row["condition"]), (256, 6, "used"))
        self.assertIsNone(row["has_warranty"])
        self.assertIsNone(row["posted_date"])

    def test_selects_requested_listing(self):
        self.assertEqual(parse_detail(page([ad(456), ad()]), "123")["listing_id"], "123")
        with self.assertRaises(ValueError):
            parse_detail(page([ad(456)]), "123")

    def test_duplicates_and_other_categories(self):
        other = ad(789)
        other["path"] = "/elanlar/elektronika/komputerler/789"
        self.assertEqual(len(parse_index(page([ad(), ad(), other]))), 1)

    def test_blocked_page(self):
        with self.assertRaises(ValueError):
            parse_index("<html>Access denied</html>")

    def test_soft_missing_detail_page_is_unavailable(self):
        with self.assertRaises(ListingUnavailable):
            parse_detail(page([], hasInitialMissingAd=True, adDetails=None), "123")
