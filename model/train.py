"""Train on both conditions; select by grouped used-only validation MAE."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.model_selection import StratifiedGroupKFold

from model.evaluate import metrics_by_condition
from model.pipeline import FEATURES, build_pipeline, features
from model.prepare import digest, group_key


def read_partition(path, expected_split):
    rows = [json.loads(line) for line in Path(path).read_text().split("\n") if line.strip()]
    if not rows:
        raise ValueError(f"Empty {expected_split} partition")
    frame = pd.DataFrame(rows)
    if frame.listing_id.duplicated().any() or not frame.dataset_split.eq(expected_split).all():
        raise ValueError("Invalid partition assignments or duplicate IDs")
    if not frame.condition.isin(["used", "new"]).all() or not frame.quality_status.eq("candidate").all():
        raise ValueError("Expected candidates with explicit used/new conditions")
    if not np.isfinite(frame.price_azn).all() or not frame.price_azn.gt(0).all():
        raise ValueError("Prices must be positive and finite")
    return frame


def candidate_configs(tune=False):
    candidates = {"median": (True, 1, {}), "random_forest": (False, 1, {}),
                  "random_forest_used_weight_3": (False, 3, {})}
    if tune:
        for leaf, depth, fraction in product((1, 2, 4), (None, 16), (1.0, 0.7)):
            if (leaf, depth, fraction) == (2, None, 1.0):
                continue  # The current unweighted baseline already covers this configuration.
            name = f"forest_leaf_{leaf}_depth_{depth}_features_{fraction}"
            candidates[name] = (False, 1, dict(min_samples_leaf=leaf, max_depth=depth, max_features=fraction))
    return candidates


def train(data_dir, output_dir, folds=5, tune=False):
    data_dir, output = Path(data_dir), Path(output_dir)
    training = read_partition(data_dir / "train.jsonl", "train")
    testing = read_partition(data_dir / "test.jsonl", "test")
    manifest = json.loads((data_dir / "split-manifest.json").read_text())
    for split in ("train", "test"):
        for line in (data_dir / f"{split}.jsonl").read_text().split("\n"):
            if not line.strip():
                continue
            row = json.loads(line)
            group = row.pop("duplicate_group")
            row.pop("dataset_split")
            if manifest["assignments"].get(row["listing_id"]) != {
                "group": group, "split": split, "row_sha256": digest(row)
            } or group_key(row) != group:
                raise ValueError("Partition does not match its split manifest")
    for field in ("listing_id", "duplicate_group"):
        if set(training[field]) & set(testing[field]):
            raise ValueError(f"Train/test overlap in {field}")
    for name, frame in (("training", training), ("test", testing)):
        if set(frame.condition) != {"used", "new"}:
            raise ValueError(f"Both conditions are required in {name}; collect more data")
    group_counts = training.groupby("condition").duplicate_group.nunique()
    if folds < 2 or group_counts.min() < folds:
        raise ValueError("Not enough independent groups per condition for requested folds")
    x, y = features(training), training.price_azn
    splits = list(StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=42).split(
        x, training.condition, groups=training.duplicate_group))
    if any(set(training.iloc[v].condition) != {"used", "new"} for _, v in splits):
        raise ValueError("Each validation fold must contain both conditions")
    candidates = candidate_configs(tune)
    cv = {}
    for name, (median, used_weight, parameters) in candidates.items():
        predictions = np.empty(len(training))
        fold_metrics = []
        for fit, validation in splits:
            pipeline = build_pipeline(median=median, **parameters)
            weights = np.where(training.iloc[fit].condition.eq("used"), used_weight, 1)
            pipeline.fit(x.iloc[fit], y.iloc[fit], model__sample_weight=weights)
            predictions[validation] = pipeline.predict(x.iloc[validation])
            fold_metrics.append(metrics_by_condition(y.iloc[validation], predictions[validation], training.iloc[validation].condition))
        cv[name] = {"pooled": metrics_by_condition(y, predictions, training.condition), "folds": fold_metrics}
        if tune:
            print(f"{name}: used CV MAE {cv[name]['pooled']['used']['mae_azn']:.2f} AZN", flush=True)
    chosen = min(cv, key=lambda name: cv[name]["pooled"]["used"]["mae_azn"])
    median, used_weight, parameters = candidates[chosen]
    pipeline = build_pipeline(median=median, **parameters)
    pipeline.fit(x, y, model__sample_weight=np.where(training.condition.eq("used"), used_weight, 1))
    # Selection is complete before holdout predictions are computed.
    predictions = pipeline.predict(features(testing))
    holdout = metrics_by_condition(testing.price_azn, predictions, testing.condition)
    baseline = build_pipeline(median=True).fit(x, y)
    reference = metrics_by_condition(testing.price_azn, baseline.predict(features(testing)), testing.condition)
    known = set(zip(training.brand, training.model))
    unseen = np.array([(b, m) not in known for b, m in zip(testing.brand, testing.model)])
    report = {
        "selected_model": chosen, "selection_metric": "pooled grouped CV used-only MAE",
        "used_sample_weight": used_weight, "features": FEATURES,
        "tuning_enabled": tune, "selected_parameters": pipeline.named_steps["model"].get_params(),
        "candidate_parameters": {name: {"median": m, "used_weight": w, "forest_params": p} for name, (m,w,p) in candidates.items()},
        "sklearn_version": sklearn.__version__,
        "split_manifest_sha256": hashlib.sha256((data_dir / "split-manifest.json").read_bytes()).hexdigest(),
        "train_counts": {k: int(v) for k,v in training.condition.value_counts().items()},
        "cv": cv, "holdout": holdout, "median_holdout": reference,
        "unseen_model_holdout": metrics_by_condition(testing.price_azn[unseen], predictions[unseen], testing.condition[unseen]),
        "note": "Exploratory asking-price holdout previously seen in EDA. Bias is prediction minus asking price. Do not tune using these holdout results.",
    }
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, output / "pipeline.joblib")
    (output / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    residuals = testing[["listing_id", "condition", "price_azn"]].copy()
    residuals["predicted_azn"] = predictions
    residuals["residual_azn"] = predictions - testing.price_azn
    residuals["unseen_model"] = unseen
    residuals.to_csv(output / "holdout-predictions.csv", index=False)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/model"))
    parser.add_argument("--output-dir", type=Path, default=Path("model/artifacts"))
    parser.add_argument("--tune", action="store_true", help="Compare a bounded forest grid using training CV only")
    args = parser.parse_args()
    result = train(args.data_dir, args.output_dir, tune=args.tune)
    print(json.dumps({k: result[k] for k in ("selected_model", "train_counts", "holdout")}, indent=2))


if __name__ == "__main__":
    main()
