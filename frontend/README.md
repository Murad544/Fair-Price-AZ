# Fair Price AZ frontend

React, TypeScript and Vite interface for the existing FastAPI service.

## Run locally

Start the API from the repository root in one terminal:

```sh
.venv/bin/python -m uvicorn api.main:app --reload
```

Start the frontend in another terminal:

```sh
cd frontend
pnpm install
pnpm dev
```

Open http://127.0.0.1:5173. The local Vite server forwards `/api/*` requests to
`http://127.0.0.1:8000/*`; neither an extra API process nor a model change is needed.
Use `API_PROXY_TARGET` in a local `.env` file for a different backend address.
See `.env.example`.

## User flows

- **Paste a link:** checks a Tap.az phone listing and shows its parsed details,
  estimated asking price, seller price, and verdict. Tracking parameters are
  removed before the canonical URL is sent. Unsupported hosts are rejected.
- **Enter details:** brand and model suggestions, used/new condition, optional
  storage and asking price. Expand “More details” for RAM, city, seller type and
  photo count. Missing fields remain missing for the saved pipeline to handle.
- Asking price is optional. Without it, the interface shows an estimate only.
- Users can cancel, switch methods, and edit inputs without stale results being
  displayed. Input values survive method switching. Checks are not saved locally.

The result uses the backend's condition-specific verdict. No confidence interval
is invented. Copy explains that these are asking-price estimates and that physical
condition, repairs and battery health still need inspection.

`src/data/models.json` contains only brand/model names observed in the training
snapshot. Suggestions are optional; users may type other names. It contains no
listing IDs, descriptions, prices, or contact details. Refresh it deliberately when
model coverage changes; it does not update automatically during training.

## Build and deployment

```sh
pnpm build
```

Output: `dist/`. For a separately hosted API, set `VITE_API_BASE_URL` to its HTTPS
origin **before building**, and include the frontend origin in the backend's
`FAIR_PRICE_CORS_ORIGINS`. Never put secrets in Vite environment variables.

Without that setting, the build sends requests to `/api` on the same origin;
production hosting must proxy that prefix to FastAPI. Vite's development proxy
is not included in static build output. `pnpm preview` only serves build files.

Fonts use Google Fonts with local system fallbacks. Icons are bundled locally.

## Checks

```sh
pnpm build
pnpm test
```

Browser tests use installed Google Chrome and simulated API responses to cover
both flows, invalid URLs, upstream failures, stale response cancellation, and mobile
layout. The test runner starts Vite when needed. A real FastAPI integration check
can also be enabled while the backend is running:

```sh
API_SMOKE=1 pnpm test
```

Playwright screenshots and reports are gitignored. No tests scrape Tap.az.
