"""Small tabular baselines; preprocessing is fitted inside each training fold."""

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

NUMERIC = ["storage_gb", "ram_gb", "photo_count"]
CATEGORICAL = ["brand", "model", "condition", "city", "seller_type"]
FEATURES = NUMERIC + CATEGORICAL


def features(frame):
    """Exclude target, free text, identifiers and split metadata explicitly."""
    return frame.reindex(columns=FEATURES).replace({None: np.nan})


def build_pipeline(median=False):
    preprocessor = ColumnTransformer([
        ("numeric", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True), NUMERIC),
        ("categorical", Pipeline([
            ("impute", SimpleImputer(strategy="constant", fill_value="unknown", keep_empty_features=True)),
            ("encode", OneHotEncoder(handle_unknown="ignore")),
        ]), CATEGORICAL),
    ])
    estimator = DummyRegressor(strategy="median") if median else RandomForestRegressor(
        n_estimators=200, min_samples_leaf=2, random_state=42, n_jobs=1)
    return Pipeline([("preprocessor", preprocessor), ("model", estimator)])
