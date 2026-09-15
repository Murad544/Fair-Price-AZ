# Initial HTTP collection validation

Date: 2026-09-07. Command: `python3 -m scraper.collect --limit 30 --max-pages 2`
(with `SSL_CERT_FILE=/etc/ssl/cert.pem` for this machine's Python installation).

## Result

- 30 unique detail records saved and exported; no failed or unavailable details.
- Two cursor batches of 24 references yielded 46 unique IDs: 30 done, 16 pending.
- The cursor advanced to `NDg`; the next run drains pending records first.
- Condition: 19 used, 10 new, 1 unknown. These counts include non-phone records.
- All 30 records contain a price and brand/category label.
- Missing: model 4, storage 5, RAM 5, condition 1, description 1.
- JSONL IDs are unique and the export contains 30 records.
- Eleven unit tests passed, including restart, deduplication, stuck cursor,
  rate limiting, robots exclusion, unavailable listings, and parse failures.

## Findings for the next step

The source puts category-like values into `Marka`: this batch contains two
`Aksesuarlar` records, one `Ehtiyat hissələri` record and one `Dublikat` record.
These need explicit treatment before training. Do not infer genuine phone models
from their titles alone: the `Dublikat` listing title resembles a normal iPhone.

Keep the raw records intact and create a separate filtering/cleaning step with
documented exclusion reasons. Review very low asking prices in context before
setting price cutoffs. An absent description or condition should remain missing.

The batch is a live convenience sample, not a representative market dataset.
Pagination is cursor-based through the frontend's unauthenticated read-only
GraphQL query. It is not a documented API contract. New listings and promotions
can shift results while collection is running; deduplication handles repeats but
does not guarantee that every listing is captured.
