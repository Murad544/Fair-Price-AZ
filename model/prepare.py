"""Prepare both conditions and persist evaluation assignments. No training."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def group_key(row):
    description = " ".join((row.get("description") or "").casefold().split())
    # Empty descriptions are not evidence of duplication. Price is deliberately absent.
    if not description:
        return digest(["listing", row["listing_id"]])
    return digest([row.get(k) for k in ("brand", "model", "storage_gb", "ram_gb", "condition")] + [description])


def prepare(input_path, output_dir):
    input_path, output = Path(input_path), Path(output_dir)
    raw = input_path.read_bytes()
    all_rows = [json.loads(line) for line in raw.decode().split("\n") if line.strip()]
    ids = [r["listing_id"] for r in all_rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate IDs in input; resolve snapshots first")
    if any(r.get("quality_status") != "candidate" for r in all_rows):
        raise ValueError("Expected cleaned candidates only")
    rows = all_rows
    if any(r.get("condition") not in ("used", "new") for r in rows):
        raise ValueError("Expected explicit used/new conditions")
    if sum(r["condition"] == "used" for r in rows) < 10:
        raise ValueError("Need at least 10 used candidates for an exploratory split")
    manifest_path = output / "split-manifest.json"
    existing = manifest_path.exists()
    manifest = json.loads(manifest_path.read_text()) if existing else {
        "version": 2, "seed": "fair-price-az-v1", "assignments": {}, "groups": {}, "initialized_conditions": []}
    if manifest.get("version") not in (1, 2):
        raise ValueError("Unsupported split manifest version")
    # Version 1 reserved only used rows. Add a new holdout once, preserving all old assignments.
    initialized = set(manifest.get("initialized_conditions", ["used"]))
    manifest["version"] = 2
    assignments, groups = manifest["assignments"], manifest["groups"]
    current_ids = {r["listing_id"] for r in rows}
    absent_test = [i for i,a in assignments.items() if a["split"] == "test" and i not in current_ids]
    if absent_test:
        raise ValueError(f"Previously reserved test IDs missing: {absent_test}. Review dataset changes before rebuilding evaluation.")
    partitions = {"train": [], "test": [], "test_related": []}
    members = defaultdict(list)
    for row in sorted(rows, key=lambda r: r["listing_id"]):
        listing_id = row["listing_id"]
        group = group_key(row)
        row_hash = digest(row)
        if listing_id in assignments:
            assignment = assignments[listing_id]
            if assignment["row_sha256"] != row_hash or assignment["group"] != group:
                raise ValueError(f"Previously assigned listing {listing_id} changed; review before replacing the split")
            split = assignment["split"]
        else:
            if group not in groups:
                # Reserve ~20% of groups initially. Later independent groups go to training.
                fraction = int(digest([manifest["seed"], group])[:8], 16) / 2**32
                groups[group] = "train" if row["condition"] in initialized or fraction >= .2 else "test"
            split = groups[group]
            if row["condition"] in initialized and split == "test":
                split = "test_related"  # Do not expand or contaminate the frozen test set.
            assignments[listing_id] = {"group": group, "split": split, "row_sha256": row_hash}
        record = dict(row, duplicate_group=group, dataset_split=split)
        partitions[split].append(record)
        members[group].append(listing_id)
    if not partitions["train"] or not partitions["test"]:
        raise ValueError("Split has an empty partition; collect more data before initializing it")
    train_models = {(r["brand"], r["model"]) for r in partitions["train"]}
    unseen = [r["listing_id"] for r in partitions["test"] if (r["brand"], r["model"]) not in train_models]
    report = {
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "used_candidates": sum(r["condition"] == "used" for r in rows),
        "new_candidates": sum(r["condition"] == "new" for r in rows),
        "conditions_by_split": {k: dict(Counter(r["condition"] for r in v)) for k,v in partitions.items()},
        "counts": {k: len(v) for k,v in partitions.items()},
        "duplicate_groups": [v for v in members.values() if len(v)>1],
        "test_models_unseen_in_train_ids": unseen,
        "train_brands": dict(Counter(r["brand"] for r in partitions["train"])),
        "test_brands": dict(Counter(r["brand"] for r in partitions["test"])),
        "note": "Exploratory holdout: EDA already examined this sample. Exact-text grouping does not catch paraphrased ads or establish device identity. Candidates still require scope review.",
    }
    manifest["initialized_conditions"] = sorted(initialized | {r["condition"] for r in rows})
    artifacts = {name + ".jsonl": "".join(json.dumps(r, ensure_ascii=False, allow_nan=False)+"\n" for r in values)
                 for name,values in partitions.items()}
    artifacts["split-manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2)+"\n"
    artifacts["preparation-report.json"] = json.dumps(report, ensure_ascii=False, indent=2)+"\n"
    if any((output / name).resolve() == input_path.resolve() for name in artifacts):
        raise ValueError("Output would overwrite the input")
    output.mkdir(parents=True, exist_ok=True)
    for name, content in artifacts.items():
        (output / (name+".tmp")).write_text(content, encoding="utf-8")
    for name in artifacts:
        (output / (name+".tmp")).replace(output / name)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/candidates.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/model"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.input, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
