import json
import tempfile
import unittest
from pathlib import Path

from model.prepare import group_key, prepare


class PreparationTests(unittest.TestCase):
    def test_price_does_not_split_matching_ads(self):
        row = {"listing_id":"1", "description":"Same phone", "price_azn":100}
        self.assertEqual(group_key(row), group_key(dict(row, listing_id="2", price_azn=200)))
        self.assertNotEqual(group_key(dict(row, description="")), group_key(dict(row, listing_id="2", description="")))

    def test_frozen_test_and_group_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root / "candidates.jsonl"
            rows=[{"listing_id":str(i), "quality_status":"candidate", "condition":"used", "brand":"Apple", "model":"iPhone 13", "description":f"Device {i}", "price_azn":500} for i in range(100)]
            def write():
                source.write_text("\n".join(json.dumps(r) for r in rows))
            write()
            prepare(source, root / "out")
            test_before=(root / "out/test.jsonl").read_bytes()
            first_test=json.loads(test_before.split(b"\n")[0])
            rows.append(dict(rows[int(first_test["listing_id"])], listing_id="101", price_azn=600))
            rows.append(dict(rows[0], listing_id="102", description="A new independent device"))
            write()
            report=prepare(source,root / "out")
            self.assertEqual(test_before,(root / "out/test.jsonl").read_bytes())
            self.assertEqual(report["counts"]["test_related"],1)
            train=[json.loads(l) for l in (root / "out/train.jsonl").read_text().split("\n") if l]
            self.assertNotIn(first_test["duplicate_group"], {r["duplicate_group"] for r in train})
            rows[int(first_test["listing_id"])]["price_azn"]=999
            write()
            with self.assertRaisesRegex(ValueError,"changed"):
                prepare(source,root / "out")
            self.assertEqual(test_before,(root / "out/test.jsonl").read_bytes())

    def test_add_new_holdout_to_legacy_manifest_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "candidates.jsonl", root / "out"
            rows = [{"listing_id": str(i), "quality_status": "candidate", "condition": "used", "brand": "Apple", "model": "iPhone 13", "description": f"Device {i}"} for i in range(100)]
            source.write_text("\n".join(json.dumps(r) for r in rows))
            prepare(source, output)
            legacy = json.loads((output / "split-manifest.json").read_text())
            original = dict(legacy["assignments"])
            legacy["version"] = 1
            legacy.pop("initialized_conditions")
            (output / "split-manifest.json").write_text(json.dumps(legacy))
            rows += [dict(rows[0], listing_id=str(i), condition="new", description=f"New device {i}") for i in range(100, 200)]
            source.write_text("\n".join(json.dumps(r) for r in rows))
            report = prepare(source, output)
            self.assertGreater(report["conditions_by_split"]["train"]["new"], 0)
            self.assertGreater(report["conditions_by_split"]["test"]["new"], 0)
            updated = json.loads((output / "split-manifest.json").read_text())
            self.assertTrue(all(updated["assignments"][i] == a for i, a in original.items()))
            before = (output / "test.jsonl").read_bytes()
            prepare(source, output)
            self.assertEqual(before, (output / "test.jsonl").read_bytes())
            first_new = next(json.loads(l) for l in before.decode().splitlines() if json.loads(l)["condition"] == "new")
            rows.append({k:v for k,v in dict(first_new, listing_id="201").items() if k not in ("dataset_split", "duplicate_group")})
            source.write_text("\n".join(json.dumps(r) for r in rows))
            report = prepare(source, output)
            self.assertEqual(report["counts"]["test_related"], 1)
            self.assertEqual(before, (output / "test.jsonl").read_bytes())
