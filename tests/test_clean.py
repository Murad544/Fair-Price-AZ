import copy
import json
from pathlib import Path
import tempfile
import unittest

from processing.clean import classify, process


def phone(**changes):
    row = dict(listing_id="123", record_type="detail", price_azn=500,
               brand="Apple iPhone", model="13", condition="used",
               storage_gb=128, ram_gb=4, description="A phone")
    return dict(row, **changes)


class CleaningTests(unittest.TestCase):
    def test_unicode_separators_are_not_record_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, notes = root / "raw.jsonl", root / "notes.json"
            notes.write_text("{}")
            description = "First\u2028second\u2029third\u0085last\nactual newline"
            source.write_text(json.dumps(phone(description=description), ensure_ascii=False) + "\r\n"
                              + json.dumps(phone(listing_id="124")), encoding="utf-8")
            report = process(source, root / "out", notes)
            self.assertEqual(report["input_records"], 2)
            with (root / "out" / "candidates.jsonl").open(encoding="utf-8") as file:
                rows = [json.loads(line) for line in file]
            self.assertEqual(rows[0]["description"], description)
            source.write_text(json.dumps(phone()) + '\n{"broken":', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "on line 2"):
                process(source, root / "out", notes)

    def test_category_overrides_phone_title(self):
        for brand in ("Aksesuarlar", "Ehtiyat hissələri", "Dublikat"):
            row = classify(phone(brand=brand, title="iPhone 17 Pro"))
            self.assertEqual(row["quality_status"], "excluded")

    def test_normalization_preserves_input_and_source(self):
        source = phone()
        original = copy.deepcopy(source)
        row = classify(source)
        self.assertEqual(source, original)
        self.assertEqual((row["brand"], row["model"]), ("Apple", "iPhone 13"))
        self.assertEqual(row["source_brand"], "Apple iPhone")

    def test_price_is_review_signal_not_deletion(self):
        self.assertEqual(classify(phone(price_azn=20))["quality_status"], "review")
        for value in (0, -10, None, True, "500"):
            self.assertIn("invalid_price", classify(phone(price_azn=value))["exclusion_reasons"])

    def test_missingness_and_new_phones(self):
        row = classify(phone(description="  ", ram_gb=None, condition="new"))
        self.assertEqual(row["quality_status"], "candidate")
        self.assertIsNone(row["description"])
        self.assertIn("missing_ram_gb", row["quality_warnings"])
        self.assertEqual(classify(phone(condition=None))["quality_status"], "review")

    def test_evidence_requires_review_and_cannot_go_stale(self):
        notes = {"123": [{"field": "description", "contains": "A phone", "reason": "test_review"}]}
        self.assertEqual(classify(phone(), notes)["quality_status"], "review")
        with self.assertRaises(ValueError):
            classify(phone(description="Changed"), notes)

    def test_partition_and_repeatability(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, notes = root / "raw.jsonl", root / "notes.json"
            notes.write_text("{}")
            records = [phone(), phone(listing_id="124", condition=None), phone(listing_id="125", brand="Aksesuarlar")]
            source.write_text("\n".join(json.dumps(r) for r in records))
            before = source.read_bytes()
            report = process(source, root / "out", notes)
            self.assertEqual(report["counts"], {"candidate": 1, "review": 1, "excluded": 1})
            outputs = {p.name:p.read_bytes() for p in (root / "out").iterdir()}
            process(source, root / "out", notes)
            self.assertEqual(outputs, {p.name:p.read_bytes() for p in (root / "out").iterdir()})
            self.assertEqual(source.read_bytes(), before)
            source.write_text(json.dumps(phone()) + "\n" + json.dumps(phone()))
            with self.assertRaises(ValueError):
                process(source, root / "out", notes)
            self.assertEqual(outputs, {p.name:p.read_bytes() for p in (root / "out").iterdir()})

    def test_condition_conflicts_require_review_without_relabeling(self):
        for description in ("Telefon çox az və səliqəli işlənib.", "Az işlənmiş telefon", "Used phone, like new", "2 ay istifadə olunub"):
            row = classify(phone(condition="new", description=description))
            self.assertEqual(row["condition"], "new")
            self.assertIn("condition_description_conflict", row["review_reasons"])
        for description in ("Yeni və işlənmiş telefonların satışı", "Heç işlənməyib", "Yeni, bağlı qutu", "Yaddaşı genişləndirmək olur"):
            self.assertEqual(classify(phone(condition="new", description=description))["quality_status"], "candidate")
        self.assertEqual(classify(phone(condition="used", description="Az işlənib"))["quality_status"], "candidate")
