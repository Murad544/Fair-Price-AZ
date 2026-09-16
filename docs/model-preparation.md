# Mixed-condition dataset preparation and training

Run `.venv/bin/python -m model.prepare` after cleaning, then
`.venv/bin/python -m model.train`. Both used and new candidates enter training.
Condition is an explicit categorical feature. Candidate status is an initial
quality screen, not proof of a genuine, working smartphone.

## Persistent evaluation assignments

- `data/model/train.jsonl`: training rows with duplicate group identifiers.
- `data/model/test.jsonl`: reserved evaluation rows of both conditions.
- `data/model/test_related.jsonl`: later ads matching reserved test groups.
- `data/model/split-manifest.json`: persistent assignments and row checksums.
- `data/model/preparation-report.json`: current counts by split and condition.

Version 2 upgrades the previous used-only manifest without changing any existing
assignment. It reserves approximately 20% of new-condition groups once. Existing
used test rows remain fixed. Future independent groups enter training; future
rows matching a test group enter `test_related`. A condition absent at initial
preparation receives its own initial reservation when it first appears.

The deterministic group hash does not guarantee exact proportions. Preparation
rejects empty overall partitions; training additionally requires both conditions
in train, test, and each validation fold. Collect more independent examples if
these checks fail. Do not delete the manifest to find a more favorable split.

Groups match normalized nonempty descriptions plus brand/model/storage/RAM and
condition, without price. Empty descriptions receive separate groups by listing
ID. This detects exact textual repetition, not paraphrases, seller identity or
all shared devices. Cross-condition relabeling can also evade this grouping.
Changed assigned rows and missing original test rows require explicit review.
Keep the manifest in local dataset backups. Run preparation once at a time.

## Selection and evaluation

The baseline uses numeric storage, RAM and photo count, plus categorical brand,
model, condition, city and seller type. Imputation and one-hot encoding are fitted
within every training fold. Identifiers, URLs, prices, descriptions and quality
metadata are not inputs. All-null year, box and warranty fields are omitted.

Five-fold stratified grouped cross-validation compares a median reference,
an unweighted random forest, and a random forest with used rows weighted 3:1.
Select the lowest pooled **used-only validation MAE**. All candidates train on
both conditions. Weight 3 is a small predefined candidate, not tuned on test data.
The selected pipeline is refitted on the full training partition only, then
assessed on the frozen holdout. The holdout never selects the winner.

Report MAE, RMSE, R², signed bias and MAE as a percentage of mean asking price
separately for used and new. Positive bias means overprediction. Mixed metrics
are supplemental. Raw MAE differences can reflect different model and price
mixes; inspect relative error and bias before claiming one condition is worse.
Report unseen-model performance separately. There is no used-only training
control yet, so these results do not prove mixed training beats used-only training.

Artifacts are local and gitignored under `model/artifacts/`: the fitted
`pipeline.joblib`, `metrics.json`, and `holdout-predictions.csv`. Load the pipeline
and call `predict(model.pipeline.features(frame))` for inference. Use
`model.verdict.verdict(predicted, actual, condition)` for the future UI: thresholds
are 15% for used and 5% for new, with exact boundaries classified as fair.
These are product rules, not statistically calibrated uncertainty intervals.

EDA has examined this sample. This is an exploratory asking-price holdout, not
an untouched benchmark or transaction-price estimate. Repeatedly running training
does not make it a fresh test. Use training validation for subsequent changes and
reserve independently collected data for a stronger final evaluation.

## Bounded hyperparameter tuning

Run `.venv/bin/python -m model.train --tune` to compare twelve unweighted forest
configurations: minimum leaf size 1/2/4, maximum depth unlimited/16, and feature
fraction 1.0/0.7. The existing forest is one of these configurations; the median
and 3× used-weight baseline remain in the comparison. All use 200 trees and the
same five grouped folds with seed 42. Both conditions remain in training.

Selection still uses pooled used-only validation MAE. Encoders and imputers are
fitted inside each fold. The holdout is evaluated only after the winner is fixed;
its scores do not choose settings. `metrics.json` records the candidate settings
and all selected estimator parameters. Searching more candidates can make the
winning validation score optimistic; this is still an exploratory benchmark.

The command replaces the normal model artifacts. Back up existing artifacts
before a tuning run. Repeat `--tune` when retraining if you want to repeat this
search; omitting it runs the original three-candidate comparison.
