# Fair Price AZ

Predict smartphone asking prices from Tap.az listings. Work proceeds by milestones,
at our own pace; the project plan's daily schedule is not used.

## Repository structure

This monorepo keeps the data pipeline, model, API, and frontend together.

```text
fair-price-az/
├── frontend/              # React + TypeScript phone price checker
├── api/                   # FastAPI prediction and live-listing endpoints
├── scraper/               # Collection and Tap.az parsing
├── processing/            # Cleaning and condition checks
├── analysis/              # Reproducible EDA scripts
├── notebooks/             # Interactive EDA
├── model/                 # Preparation, training, evaluation, and verdicts
├── tests/                 # Python regression tests
├── docs/                  # Data policies and workflow documentation
├── data/                  # Local datasets and persistent split assignments
├── reports/               # Generated local EDA reports
├── requirements-eda.txt
├── requirements-model.txt
├── requirements-api.txt
├── .gitignore
└── README.md
```

Run Python commands from the repository root. Generated datasets, reports, and
model artifacts stay local and are excluded from Git. The frontend lives in `frontend/`; its dependencies and generated build files
are also excluded from Git.

## Run the API

```sh
.venv/bin/python -m pip install -r requirements-api.txt
.venv/bin/python -m uvicorn api.main:app --reload
```

Open http://127.0.0.1:8000/docs to try `GET /health`, `POST /predict`, and
`POST /predict-from-url`. The API loads the existing model once at startup and
uses the same preprocessing and verdict rules. It does not retrain the model.
See [API usage](docs/api.md) for request examples, configuration and error codes.

## Run the frontend

With the API running, open another terminal:

```sh
cd frontend
pnpm install
pnpm dev
```

Open http://127.0.0.1:5173. Users can paste a Tap.az phone link or enter details
manually. Results show the estimate and, when an asking price is supplied, a
condition-specific verdict. The local frontend proxies requests to the API on
port 8000. See [frontend setup](frontend/README.md) for deployment and browser tests.

Validation: `pnpm build` and `pnpm test` from `frontend/`.

## Collect a small batch

Python 3; no third-party dependencies are required.

```sh
SSL_CERT_FILE=/etc/ssl/cert.pem python3 -m scraper.collect --limit 200 --max-pages 9
```

The collector checks robots.txt, discovers up to two batches of 24 listing URLs,
and attempts up to 30 detail pages. It waits at least three seconds between
requests. Add `--user-agent 'FairPriceAZ/0.2 (+your real contact URL or email)'`
when you have a project contact to provide.

Output:

- `data/raw/listings.sqlite3`: saved details, pending queue and pagination cursor.
- `data/raw/listings.jsonl`: regenerated export of all successfully saved details.
- A terminal report with counts and missing fields.

Run the same command to continue from the saved queue. `--limit` applies to new
detail attempts in that run, not the total database size. Already collected IDs
are skipped. Use a different `--db` and `--output` for a fresh snapshot. Run one
collector at a time against a database. This is a resumable snapshot collector;
it does not refresh previously saved prices. A moving live feed may shift across
cursor requests, so collection does not guarantee complete coverage.

HTTP 404/410 marks a listing unavailable and continues. A matching listing ID that now has a different
category path is marked `out_of_scope` and skipped; it counts toward the run's
detail-attempt limit. Unexpected missing records still stop the run.
Other HTTP errors
(including 403/429), network failures, unexpected redirects and parsing errors
stop the run with progress preserved. Rerun only after investigating the cause.
Ctrl-C also preserves progress and exports completed records.

If a macOS Python installation reports `CERTIFICATE_VERIFY_FAILED` because its
default CA bundle is missing, use the system bundle (TLS verification stays on):

```sh
SSL_CERT_FILE=/etc/ssl/cert.pem python3 -m scraper.collect --limit 30 --max-pages 2
```

## Parse saved HTML

Python 3, with no third-party dependencies for this initial parser.

```sh
python3 -m scraper.run /tmp/fair-price-index.html --output data/raw/index-sample.jsonl
python3 -m scraper.run /tmp/fair-price-detail.html --listing-id 48625206 --output data/raw/detail-sample.jsonl
python3 -m unittest discover -s tests
```

The `/tmp` paths refer to pages downloaded during the initial inspection. Supply
your own saved HTML paths for subsequent runs. Output files must not already exist.

The detail parser reads `__NEXT_DATA__` → `props.pageProps.apolloState` in
server-rendered HTML. Discovery uses the site's unauthenticated, read-only
`POST /graphql` listing query, matching its public frontend's cursor pagination.
This is an undocumented website interface, not a supported developer API; it
can change. `?page=2` still returned `ads(first:24)` and did not advance the cursor
during inspection, so the collector does not use page-number URLs.

Discovery selects regular search results and excludes the separate random VIP
section. IDs deduplicate repeated search results. Details still include new and
used phones, shops, and possible accessories.

## Clean and review the collected data

```sh
python3 -m processing.clean
python3 -m unittest discover -s tests
```

This reads `data/raw/listings.jsonl` and writes four files to `data/processed/`:

- `candidates.jsonl`: passes initial checks, with normalized brand/model names.
- `review.jsonl`: uncertain records with explicit review reasons.
- `excluded.jsonl`: accessories, spare parts, replicas, non-detail rows or invalid prices.
- `quality-report.json`: counts, missingness warnings and source/policy checksums.

Raw data is preserved. Processed data is also gitignored. Re-running the same
input and review notes produces the same outputs. Duplicate input IDs cause an
error rather than silently choosing a price snapshot. Use `--input`,
`--output-dir` and `--annotations` to process a different dataset.

See `docs/cleaning-policy.md` for rules, limitations and sample findings.

## Rerun exploratory analysis

The EDA dependencies are installed in `.venv`. To set them up on another machine:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-eda.txt
```

After collecting a batch, regenerate cleaning and analysis:

```sh
.venv/bin/python -m processing.clean
.venv/bin/python -m analysis.eda
```

Read `reports/eda/eda.md`, view `reports/eda/overview.png`, or inspect
`reports/eda/summary.json`. The six charts cover prices, brand/condition coverage,
missingness, model frequency, prices by brand, and storage coverage, each separated
by used/new condition.
Reports are regenerated and gitignored. No model is trained by this command.
Counts refer to candidates, not verified devices. The analysis explicitly shows
both conditions while retaining used-only diagnostics for the primary use case.

## Prepare and train on both conditions

```sh
.venv/bin/python -m pip install -r requirements-model.txt
.venv/bin/python -m model.prepare
.venv/bin/python -m model.train
```

Run after cleaning. This writes training/test files and a persistent split manifest
under `data/model/`. Existing test assignments stay fixed when more data arrives.
New ads matching a test group are set aside. Keep the manifest; see
`docs/model-preparation.md` for grouping rules, limitations and current counts.
Preparation preserves the original used holdout and reserves new-condition groups
once. Training compares a median baseline, random forest, and used-weighted random
forest with five-fold grouped validation. Selection uses **used-only MAE**.
The holdout reports used/new MAE, RMSE, R² and signed bias separately.

Open `notebooks/01_eda.ipynb` for reproducible EDA with both conditions.
Model outputs are in `model/artifacts/metrics.json`, `pipeline.joblib`, and
`holdout-predictions.csv`. The reusable verdict function in `model/verdict.py`
uses 15% for used and 5% for new. The API and frontend both expose this comparison.

## Latest tuning run

Run `.venv/bin/python -m model.train --tune` to repeat the bounded search.
It compares twelve unweighted forest configurations, the used-weighted baseline,
and the median reference using identical grouped folds. All train on both conditions.

The latest run uses 1,810 training listings (986 used, 824 new), with 41 used and
158 new reserved for evaluation. Selected settings: 200 trees, maximum depth 16,
minimum leaf size 1, and feature fraction 0.7, with no additional used weighting.

| Metric | Untuned forest | Tuned forest |
| --- | ---: | ---: |
| Used grouped validation MAE (AZN) | 165.62 | 161.40 |
| Used holdout MAE (AZN) | 166.20 | 171.92 |
| New holdout MAE (AZN) | 104.86 | 104.89 |
| Used holdout RMSE (AZN) | 265.77 | 290.93 |
| Used holdout bias (AZN) | +24.36 | +7.14 |

The winner is selected from training validation only. Lower validation error did
not translate into lower used holdout error; this experiment does not establish
an improvement. Used holdout MAE is 25.06% of mean asking price, above the 20%
target. Do not keep changing parameters based on this holdout.

The current `model/artifacts/pipeline.joblib` contains the tuned model. The prior
model, metrics and predictions are preserved locally under
`model/artifacts/before-tuning-20260915-160248/`. See `docs/model-preparation.md`
for the tuning workflow. All 30 regression tests pass, including the tuning path.

## Original exploratory baseline results

Snapshot: 1,267 candidates (532 used, 735 new). Training contains 491 used and
577 new; the frozen holdout contains 41 used and 158 new. The original 41 used
test rows are preserved. Later raw collection is not included until reprocessing.

The unweighted random forest wins used-only grouped CV MAE: **174.57 AZN**,
versus **179.66 AZN** with 3× used weights and **631.32 AZN** for the median baseline.

| Holdout condition | Rows | MAE (AZN) | RMSE (AZN) | Bias (AZN) | MAE / mean price |
| --- | ---: | ---: | ---: | ---: | ---: |
| Used (primary) | 41 | 183.26 | 262.51 | +30.05 | 26.71% |
| New | 158 | 135.32 | 221.36 | +6.20 | 8.52% |

Positive bias means overprediction. The median holdout MAE is 582.18 AZN for used
and 861.72 AZN for new. Used performance still misses the plan's 20% target;
the small exploratory holdout does not establish production readiness. Used-only
training has not been compared, so this does not prove that adding new phones
improves used predictions. Subsequent changes should use training validation,
not tuning against these holdout results.

## Data interpretation

- Prices are asking prices, not verified sale prices.
- The telephone category includes accessories; index records are candidates,
  not a cleaned smartphone training dataset.
- Preserve Azerbaijani property labels in `raw_properties` for later reprocessing.
- `Yeni?` maps to condition; `Yaddaş` may contain both storage and RAM.
- `source_updated_at` is not the original posting date.
- Missing box, warranty, year and posting date stay null, not false or guessed.
- A shop marker identifies a shop; absence alone does not prove private ownership.
- Index and detail samples overlap. Do not concatenate them as independent training rows.
- Contact/user objects and image URLs are omitted. Descriptions are seller text
  and can still contain personal information. Raw data stays out of Git.

Inspection on 2026-09-07: https://tap.az/robots.txt did not disallow the phone
category for the generic user agent. Recheck before collecting. Future collection
should identify the project, space requests at least three seconds apart, and
stop on blocks/rate limits rather than retry aggressively.
