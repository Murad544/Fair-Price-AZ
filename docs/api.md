# FastAPI service

The API serves the existing `model/artifacts/pipeline.joblib`. Starting the API
never trains or modifies the model. The pipeline is loaded once per process at
startup; restart the server after replacing the artifact. A missing, unreadable,
or incompatible model prevents startup. Load only trusted joblib artifacts.

## Install and run

From the repository root:

```sh
.venv/bin/python -m pip install -r requirements-api.txt
.venv/bin/python -m uvicorn api.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive Swagger documentation.
The JSON contract is at `/openapi.json`. Use a single worker while the live
fetcher uses an in-process request lock and rate limiter.

## Endpoints

### GET /health

Returns `status: "ok"` and `model_version`, the SHA-256 of the loaded artifact.
It does not fetch Tap.az or read the training dataset.

### POST /predict

```sh
curl -sS http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"brand":"Apple","model":"iPhone 13","condition":"used","storage_gb":128,"actual_price_azn":650}'
```

Required: `brand`, `model`, `condition` (`used` or `new`).
Optional: positive integer `storage_gb` and `ram_gb`, non-negative integer
`photo_count`, `city`, and `seller_type` (`shop`, `private`, or null).
Missing optional features remain missing and use the saved pipeline's imputers.
Use canonical training labels, for example `Samsung` and `Galaxy S23`.
`Apple iPhone` plus `13` is normalized to `Apple` plus `iPhone 13`.
The API rejects unknown fields, invalid conditions, and invalid numeric inputs.

Optional `actual_price_azn` is the positive, finite asking price to compare.
It is never passed into model features. Without it, comparison fields are null.

Response fields:

- `predicted_price_azn`: estimated asking price, rounded to two decimal places.
- `currency`: `AZN`.
- `condition`: the submitted condition.
- `actual_price_azn`: submitted asking price, or null.
- `difference_pct`: `(actual - prediction) / prediction * 100`, or null.
- `verdict`: `Fair price`, `Overpriced by X%`, or `Good deal — X% below predicted`.
- `model_version`: fingerprint of the served artifact.

Verdicts reuse the existing rules: 15% for used phones, 5% for new phones.
Exact threshold boundaries are fair. Comparisons use the unrounded prediction.
These rules are not confidence intervals. Predictions estimate asking prices,
not verified sale prices; unknown models can have poor accuracy.

### POST /predict-from-url

```sh
curl -sS http://127.0.0.1:8000/predict-from-url \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://tap.az/elanlar/elektronika/telefonlar/12345678"}'
```

Replace the example ID with an existing listing. Only HTTPS URLs on `tap.az`
with the exact phone-category path and numeric ID are accepted. A trailing slash
is allowed. Query parameters, fragments, custom ports and other hosts are rejected.
Redirects are not followed. The URL is validated before any network request.

The fetcher checks robots.txt, respects crawl delays and the scraper's minimum
three-second spacing, parses the requested listing, and applies general cleaning
rules. Conflicting conditions, missing required fields, accessories, replicas and
other review records are rejected. Historical manual annotations are not applied
to live pages. Each lookup requires at least two upstream requests and can take
several seconds; network requests time out individually after 30 seconds.

The response includes prediction fields plus `listing_id`, canonical `url`, and
normalized `features`. Raw descriptions, contact information and HTML are not
returned or saved. No training rows or split assignments are changed.

## Errors

| HTTP status | Meaning |
| --- | --- |
| 422 | Invalid input, unsupported listing, or listing requiring review |
| 404 | Listing removed or moved outside the phone category |
| 429 | Another live lookup is running; retry later |
| 502 | Upstream network, robots, redirect, or parsing failure |
| 503 | Upstream blocked/limited/unavailable, or prediction failed |
| 504 | Upstream timeout |

The fetcher does not automatically retry blocks or rate limits. Manual predictions
remain available while a live lookup is running. Live-fetch spacing is per process,
so use one worker until a shared limiter is introduced for deployment.

## Environment variables

- `FAIR_PRICE_MODEL_PATH`: trusted local artifact path; defaults to the repository's
  `model/artifacts/pipeline.joblib`, independent of the working directory.
- `FAIR_PRICE_USER_AGENT`: scraper identification; set your project contact before
  public use. Defaults to the existing research-prototype identification.
- `FAIR_PRICE_CORS_ORIGINS`: comma-separated allowed frontend origins. Defaults to
  `http://localhost:5173,http://127.0.0.1:5173`. CORS is not authentication.

The API uses the installed `certifi` CA bundle by default, so it does not depend
on the Python installation having a system CA file. Certificate and hostname
verification remain enabled. `SSL_CERT_FILE` overrides the bundle when needed.
For example, to use the macOS system CA:

```sh
SSL_CERT_FILE=/etc/ssl/cert.pem .venv/bin/python -m uvicorn api.main:app --reload
```

## Verification

```sh
.venv/bin/python -m unittest discover -s tests
```

API tests use a temporary fitted pipeline and simulated upstream HTML/errors.
They cover prediction parity, both conditions, verdicts, validation, URL restrictions,
normalization, cleaning, upstream failures, startup, docs, and CORS. These tests
make no network calls. Actual Tap.az availability is independent of offline tests.

Startup and test lifespans follow the official FastAPI documentation:
https://fastapi.tiangolo.com/advanced/events/ and
https://fastapi.tiangolo.com/advanced/testing-events/.
