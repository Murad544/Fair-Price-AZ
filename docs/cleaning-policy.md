# Initial cleaning policy

Version 1, validated against 30 listings collected on 2026-09-07.

The goal is to separate clear exclusions from uncertainty while retaining the
original dataset. Outputs are candidate, review and excluded JSONL files, plus
a count report. Each row belongs to exactly one file. This is an initial quality
screen, not a verified training dataset or comprehensive smartphone classifier.

## Rules

| Evidence | Action |
| --- | --- |
| Source brand/category `Aksesuarlar` | Exclude as accessory |
| `Ehtiyat hissələri` | Exclude as spare parts |
| `Dublikat` | Exclude as replica |
| Non-detail record or non-numeric/non-positive price | Exclude |
| Price below 50 or above 10,000 AZN | Review, not exclusion; provisional inspection band |
| Missing brand/model or unknown condition | Review |
| Missing storage, RAM or description | Preserve missingness and attach warning |
| Invalid non-positive/non-integer storage or RAM | Set to null and review |
| New condition | Retain alongside used; condition remains available for later selection |
| Sample-specific description evidence | Review using the documented observations file |

Source category labels take precedence over phone-like titles. Brand `Apple
iPhone` becomes `Apple`, and model `13` becomes `iPhone 13`; source values remain
in `source_brand`, `source_model` and `raw_properties`. Whitespace is normalized
in brand/model/city/color. Empty descriptions become null, and other descriptions
are preserved. Missing box, warranty and year are not inferred.

The observations in `processing/review-observations.json` record three issues
found by reading this sample: inconsistent model, a new condition conflicting
with a reported replacement battery, and reported major damage. Each observation
has an exact supporting description excerpt. If that evidence changes, cleaning
stops so a stale observation is not silently reused. These are manual sample
observations, not a general language classifier. Other repairs, damage, condition
conflicts, mislabeled accessories or non-smartphones may remain among candidates.

The raw descriptions may contain personal information. Raw and processed data
remain local and gitignored. The version-controlled observations contain only
short product-condition excerpts, not contact details.

## Validation result

- 22 candidates: 16 used and 6 new.
- 4 for review: model mismatch/low price, major damage, condition conflict, and
  missing condition. One record can have multiple reasons.
- 4 exclusions: 2 accessories, 1 spare-parts listing, 1 replica.
- Candidate brands: Apple 13, Xiaomi 5, Samsung 3, Honor 1.
- Input is unchanged, partitions contain all 30 IDs exactly once, and repeat
  processing is deterministic.
- 17 tests passed across collection, parsing and cleaning.

Next: collect a bounded larger sample, rerun these checks, inspect the review
queue and a sample of candidates, and refine scope for damaged devices and
model/condition conflicts before training. The current sample is too small and
too concentrated in a few brands to establish market coverage.

## Condition checks added after collection

The parser preserves `Yeni?` in raw properties and maps `Bəli` to `new` and
`Xeyr` to `used`. Unsupported values remain unknown and enter review. A bare
“Yeni” string is not treated as proof of a sealed phone.

Cleaning now sends new-labelled records with narrow usage claims (for example,
“az işlənib”, “2 ay istifadə olunub”, or “like new”) to condition-conflict review.
It preserves the source label instead of silently relabelling the phone. Generic
shop text about selling new and used phones, negated “unused” language, and
storage expansion do not trigger the rule. Missing evidence does not verify a
condition; repairs, keyword spam and other languages still require manual review.
Existing unchanged records retain their checksums; affected assigned records
cause preparation to stop for review under the existing manifest policy.
