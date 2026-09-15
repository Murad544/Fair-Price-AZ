import json
from pathlib import Path
import tempfile
import unittest

import joblib
import numpy as np
import pandas as pd

from model.evaluate import metrics_by_condition
from model.pipeline import FEATURES, build_pipeline, features
from model.prepare import prepare
from model.train import train
from model.verdict import verdict


class ModelTests(unittest.TestCase):
    def test_condition_metrics_do_not_hide_used_errors(self):
        result = metrics_by_condition([100, 1000, 1000], [200, 1000, 1000], ["used", "new", "new"])
        self.assertEqual(result["used"]["mae_azn"], 100)
        self.assertEqual(result["used"]["bias_azn"], 100)
        self.assertEqual(result["new"]["mae_azn"], 0)
        self.assertLess(result["all"]["mae_azn"], result["used"]["mae_azn"])

    def test_verdict_condition_boundaries_and_invalid_input(self):
        for condition, threshold in (("used", 15), ("new", 5)):
            for price in (100 - threshold, 100 + threshold):
                self.assertEqual(verdict(100, price, condition), "Fair price")
            self.assertTrue(verdict(100, 101 + threshold, condition).startswith("Overpriced"))
            self.assertTrue(verdict(100, 99 - threshold, condition).startswith("Good deal"))
        for values in ((0, 100, "used"), (100, float("nan"), "new"), (100, 100, "unknown")):
            with self.assertRaises(ValueError):
                verdict(*values)

    def test_condition_is_predictive_and_unknown_features_work(self):
        frame = pd.DataFrame([dict(brand="Apple", model="iPhone", condition=c, price_azn=p) for c,p in [("used",100), ("new",200)] * 10])
        x = features(frame)
        self.assertNotIn("price_azn", FEATURES)
        pipeline = build_pipeline().fit(x, frame.price_azn)
        predictions = pipeline.predict(x.iloc[:2])
        self.assertLess(predictions[0], predictions[1])
        unseen = features(pd.DataFrame([dict(brand="Unseen", model="Unknown", condition="used")]))
        self.assertTrue(np.isfinite(pipeline.predict(unseen)).all())

    def test_training_selection_and_artifact_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [dict(listing_id=str(i), quality_status="candidate", condition="used" if i % 2 else "new", brand="Apple", model="iPhone", description=f"Device {i}", price_azn=100 if i % 2 else 200) for i in range(100)]
            source = root / "candidates.jsonl"
            source.write_text("\n".join(json.dumps(r) for r in rows))
            prepare(source, root / "data")
            report = train(root / "data", root / "artifacts", folds=2)
            best = min(report["cv"], key=lambda k: report["cv"][k]["pooled"]["used"]["mae_azn"])
            self.assertEqual(report["selected_model"], best)
            self.assertEqual(set(report["train_counts"]), {"used", "new"})
            pipeline = joblib.load(root / "artifacts/pipeline.joblib")
            self.assertTrue(np.isfinite(pipeline.predict(features(pd.DataFrame(rows[:2])))).all())
            path = root / "data/test.jsonl"
            testing = [json.loads(l) for l in path.read_text().splitlines()]
            testing[0]["price_azn"] += 1
            path.write_text("\n".join(json.dumps(r) for r in testing))
            with self.assertRaisesRegex(ValueError, "manifest"):
                train(root / "data", root / "invalid", folds=2)
