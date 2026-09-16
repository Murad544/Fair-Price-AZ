"""Load a trusted local artifact and reuse training-time preprocessing."""

import hashlib
import io
import math
from pathlib import Path

import joblib
import pandas as pd

from api.schemas import PhoneFeatures, PredictionResponse
from model.pipeline import FEATURES, features
from model.verdict import verdict


class Predictor:
    def __init__(self, model_path):
        # Read once so the fingerprint identifies the exact loaded bytes.
        payload = Path(model_path).read_bytes()
        self.version = hashlib.sha256(payload).hexdigest()
        self.pipeline = joblib.load(io.BytesIO(payload))
        if list(getattr(self.pipeline, "feature_names_in_", [])) != FEATURES:
            raise ValueError("Saved pipeline does not match the API feature schema")

    def predict(self, phone: PhoneFeatures, actual_price=None):
        frame = pd.DataFrame([phone.model_dump(include=set(FEATURES))])
        predicted = float(self.pipeline.predict(features(frame))[0])
        if not math.isfinite(predicted) or predicted <= 0:
            raise ValueError("Model returned an invalid price")
        return PredictionResponse(
            predicted_price_azn=round(predicted, 2), condition=phone.condition,
            actual_price_azn=actual_price,
            difference_pct=round((actual_price - predicted) / predicted * 100, 2) if actual_price is not None else None,
            verdict=verdict(predicted, actual_price, phone.condition) if actual_price is not None else None,
            model_version=self.version,
        )
