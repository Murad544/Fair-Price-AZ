"""Classify raw listing records without modifying the source dataset."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import unicodedata

from processing.condition import condition_conflict

VERSION = "1"
EXCLUSIONS = {
    "aksesuarlar": "accessory",
    "ehtiyat hissələri": "spare_parts",
    "dublikat": "replica",
}


def reject_constant(value):
    raise ValueError(f"Non-standard JSON numeric constant: {value}")


def text(value):
    return " ".join(value.split()) if isinstance(value, str) else None


def key(value):
    return unicodedata.normalize("NFC", text(value) or "").replace("İ", "i").casefold()


def classify(source, annotations=None):
    row = dict(source)
    reasons = []
    warnings = []
    excluded = []
    category = EXCLUSIONS.get(key(source.get("brand")))
    if category:
        excluded.append(category)
    if source.get("record_type") != "detail":
        excluded.append("not_detail_record")
    price = source.get("price_azn")
    valid_price = type(price) in (int, float) and math.isfinite(price) and price > 0
    if not valid_price:
        excluded.append("invalid_price")
    elif price < 50 or price > 10000:
        reasons.append("price_outside_review_band")

    for field in ("brand", "model", "city", "color"):
        row[field] = text(source.get(field)) or None
    row["source_brand"] = source.get("brand")
    row["source_model"] = source.get("model")
    if key(row["brand"]) == "apple iphone":
        row["brand"] = "Apple"
        if row["model"] and not key(row["model"]).startswith("iphone"):
            row["model"] = "iPhone " + row["model"]

    for field in ("brand", "model"):
        if not row[field]:
            reasons.append("missing_" + field)
    if source.get("condition") not in ("used", "new"):
        row["condition"] = None
        reasons.append("missing_or_unknown_condition")
    if condition_conflict(source.get("condition"), source.get("description")):
        reasons.append("condition_description_conflict")
    for field in ("storage_gb", "ram_gb"):
        value = source.get(field)
        if value is None:
            warnings.append("missing_" + field)
        elif type(value) is not int or value <= 0:
            row[field] = None
            reasons.append("invalid_" + field)
    if not text(source.get("description")):
        row["description"] = None
        warnings.append("missing_description")

    # Reviewed observations apply only while their exact evidence remains present.
    evidence = []
    for annotation in (annotations or {}).get(source["listing_id"], []):
        field = annotation["field"]
        quote = annotation["contains"]
        if not quote or quote not in (source.get(field) or ""):
            raise ValueError(f"Stale review evidence for {source['listing_id']}: {field}")
        reasons.append(annotation["reason"])
        evidence.append(annotation)

    row.update({
        "cleaning_version": VERSION,
        "quality_status": "excluded" if excluded else "review" if reasons else "candidate",
        "exclusion_reasons": excluded,
        "review_reasons": sorted(set(reasons)),
        "quality_warnings": warnings,
        "review_evidence": evidence,
    })
    return row


def process(input_path, output_dir, annotations_path):
    input_path, output_dir = Path(input_path), Path(output_dir)
    # Never permit output to replace the input or review policy.
    names = ("candidates.jsonl", "review.jsonl", "excluded.jsonl", "quality-report.json")
    protected = {input_path.resolve(), Path(annotations_path).resolve()}
    if any((output_dir / name).resolve() in protected for name in names):
        raise ValueError("Output would overwrite a source file")
    raw = input_path.read_bytes()
    annotations_bytes = Path(annotations_path).read_bytes()
    annotations = json.loads(annotations_bytes)
    rows = []
    seen = set()
    # JSONL records end at LF. Unicode separators can occur inside JSON strings.
    for number, line in enumerate(raw.decode("utf-8").split("\n"), 1):
        if not line.strip():
            continue
        try:
            source = json.loads(line, parse_constant=reject_constant)
        except ValueError as error:
            raise ValueError(f"Invalid JSON in {input_path} on line {number}: {error}") from error
        if not isinstance(source, dict):
            raise ValueError(f"Expected a listing object on line {number}")
        listing_id = source.get("listing_id")
        if not isinstance(listing_id, str) or not listing_id.isdecimal():
            raise ValueError(f"Invalid listing ID on line {number}")
        if listing_id in seen:
            raise ValueError(f"Duplicate listing ID {listing_id}; select a snapshot before cleaning")
        seen.add(listing_id)
        rows.append(classify(source, annotations))

    groups = {status: [r for r in rows if r["quality_status"] == status]
              for status in ("candidate", "review", "excluded")}
    report = {
        "cleaning_version": VERSION,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "annotations_sha256": hashlib.sha256(annotations_bytes).hexdigest(),
        "input_records": len(rows),
        "counts": {k: len(v) for k, v in groups.items()},
        "exclusion_reasons": dict(Counter(x for r in rows for x in r["exclusion_reasons"])),
        "review_reasons": dict(Counter(x for r in rows if r["quality_status"] == "review" for x in r["review_reasons"])),
        "warnings": dict(Counter(x for r in rows for x in r["quality_warnings"])),
        "candidate_conditions": dict(Counter(r["condition"] for r in groups["candidate"])),
        "candidate_brands": dict(Counter(r["brand"] for r in groups["candidate"])),
        "unused_annotation_ids": sorted(set(annotations) - seen),
        "note": "Candidates pass initial checks; they are not verified authentic, working smartphones or a training-ready dataset. Review is not automatic exclusion.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for status, name in zip(groups, names):
        content = "".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in groups[status])
        (output_dir / (name + ".tmp")).write_text(content, encoding="utf-8")
    (output_dir / "quality-report.json.tmp").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in names:
        (output_dir / (name + ".tmp")).replace(output_dir / name)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/listings.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--annotations", type=Path,
                        default=Path(__file__).with_name("review-observations.json"))
    args = parser.parse_args()
    print(json.dumps(process(args.input, args.output_dir, args.annotations), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
