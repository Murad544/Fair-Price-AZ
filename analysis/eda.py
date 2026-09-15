"""Run with: .venv/bin/python -m analysis.eda"""

import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("reports/.matplotlib").resolve()))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def table(frame):
    """Small Markdown table without an optional tabulate dependency."""
    frame = frame.copy().fillna("unknown")
    escape = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(map(escape, frame.columns)) + " |",
             "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    lines.extend("| " + " | ".join(map(escape, row)) + " |" for row in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def run(input_path, output_dir):
    source = Path(input_path)
    raw = source.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").split("\n") if line.strip()]
    if not rows:
        raise ValueError("No candidates to analyze; collect and clean first")
    df = pd.DataFrame(rows)
    if df.listing_id.duplicated().any():
        raise ValueError("Duplicate listing IDs; resolve snapshots before analysis")
    if not df.quality_status.eq("candidate").all():
        raise ValueError("EDA expects the candidates output from processing.clean")
    df["price_azn"] = pd.to_numeric(df.price_azn, errors="raise")
    if not df.price_azn.between(0, float("inf"), inclusive="neither").all():
        raise ValueError("Prices must be positive and finite")
    used = df[df.condition.eq("used")]
    new = df[df.condition.eq("new")]
    fields = ["brand", "model", "storage_gb", "ram_gb", "condition", "city",
              "seller_type", "description", "photo_count", "year", "has_box", "has_warranty", "posted_date"]
    missing = pd.DataFrame({"field": fields,
        "all_missing_pct": [round(df[f].isna().mean()*100, 1) for f in fields],
        "new_missing_pct": [round(new[f].isna().mean()*100, 1) if len(new) else None for f in fields],
        "used_missing_pct": [round(used[f].isna().mean()*100, 1) if len(used) else None for f in fields]})
    brand = pd.crosstab(df.brand, df.condition).reindex(columns=["used", "new"], fill_value=0)
    brand = brand.sort_values("used", ascending=False)
    prices = df.groupby("condition").price_azn.agg(count="count", minimum="min", median="median", mean="mean", maximum="max").round(1).reset_index()
    models = used.groupby(["brand", "model"], dropna=False).size().sort_values(ascending=False)
    model_counts = pd.crosstab([df.brand, df.model], df.condition).reindex(columns=["used", "new"], fill_value=0)
    model_counts["total"] = model_counts.sum(axis=1)
    top_models = model_counts.sort_values("total", ascending=False).head(15).reset_index()
    repeated = models[models >= 5]
    # A review signal, not deduplication: identical commercial ads may represent different devices.
    signatures = df[["brand", "model", "storage_gb", "condition", "price_azn"]].fillna("unknown").astype(str)
    signatures["description"] = df.description.fillna("").str.casefold().str.split().str.join(" ")
    eligible = signatures[signatures.description.ne("")]
    potential_duplicates = int(eligible.duplicated(keep=False).sum())

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(3, 2, figsize=(16, 15), layout="constrained")
    colors = {"used": "#236b8e", "new": "#df8e32"}
    bins = 30
    for condition in ("used", "new"):
        sample = df.loc[df.condition.eq(condition), "price_azn"]
        if len(sample):
            axes[0, 0].hist(sample, bins=bins, range=(0, df.price_azn.max()), alpha=.55,
                            color=colors[condition], label=f"{condition} (n={len(sample)})")
    axes[0, 0].set(title="Asking-price distribution", xlabel="AZN", ylabel="Listings")
    axes[0, 0].legend()
    brand.plot.barh(stacked=True, color=[colors["used"], colors["new"]], ax=axes[0, 1])
    axes[0, 1].set(title="Brand coverage by condition", xlabel="Listings", ylabel="")
    axes[0, 1].invert_yaxis()
    missing.set_index("field")[["used_missing_pct", "new_missing_pct"]].plot.barh(ax=axes[1, 0], color=[colors["used"], colors["new"]])
    axes[1, 0].set(title="Missing fields by condition", xlabel="Missing (%)", ylabel="", xlim=(0, 110))
    axes[1, 0].legend(["Used candidates", "New candidates"], fontsize=8)
    axes[1, 0].invert_yaxis()
    if len(top_models):
        labels = top_models.brand + " " + top_models.model
        axes[1, 1].barh(labels, top_models.used, color=colors["used"], label="used")
        axes[1, 1].barh(labels, top_models.new, left=top_models.used, color=colors["new"], label="new")
        axes[1, 1].legend()
        axes[1, 1].invert_yaxis()
    axes[1, 1].set(title="Most frequent models by condition", xlabel="Listings")
    frequent = df.groupby(["brand", "condition"]).size().loc[lambda s: s >= 5].index
    if len(frequent):
        axes[2, 0].boxplot([df.loc[df.brand.eq(b) & df.condition.eq(c), "price_azn"] for b,c in frequent],
                          tick_labels=[f"{b}\n{c}" for b,c in frequent])
        axes[2, 0].tick_params(axis="x", rotation=60, labelsize=7)
    axes[2, 0].set(title="Asking prices by brand and condition (n ≥ 5)", ylabel="AZN")
    counts = pd.crosstab(df.storage_gb, df.condition).reindex(columns=["used", "new"], fill_value=0)
    counts.index = [f"{int(x)} GB" for x in counts.index]
    if len(counts):
        counts.plot.bar(ax=axes[2, 1], color=[colors["used"], colors["new"]])
    axes[2, 1].tick_params(axis="x", rotation=30)
    axes[2, 1].set(title=f"Storage coverage ({df.storage_gb.isna().sum()} missing)", ylabel="Listings", xlabel="")
    fig.suptitle(f"Fair Price AZ • initial EDA • {len(df)} candidates / {len(used)} used", fontsize=20)
    fig.savefig(output / "overview.png", dpi=130)
    plt.close(fig)

    summary = {"input_sha256": hashlib.sha256(raw).hexdigest(), "candidates": len(df), "used": len(used),
        "new": len(new), "distinct_models": len(model_counts), "distinct_new_models": len(new.groupby(["brand", "model"])), "distinct_used_models": len(models),
        "used_models_with_at_least_5": len(repeated), "used_rows_in_models_with_at_least_5": int(repeated.sum()),
        "potential_duplicate_rows": potential_duplicates,
        "missingness": missing.to_dict(orient="records"), "prices_by_condition": prices.to_dict(orient="records")}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    report = f"""# Fair Price AZ — exploratory analysis

Source: `{source}`. SHA-256: `{summary['input_sha256']}`.
This report is regenerated by `.venv/bin/python -m analysis.eda` after cleaning.

![Dataset overview](overview.png)

## What the sample supports

There are {len(df)} candidates: {len(used)} used and {summary['new']} new listings.
Used listings cover {len(models)} brand/model combinations; {len(repeated)} combinations have
at least five examples, accounting for {int(repeated.sum())} used listings. Five examples is
a coverage diagnostic, not a guarantee of sufficient training data.

{table(prices)}

These are asking prices. New and used samples contain different models and sellers,
so differences in their average prices do not measure depreciation. Brand boxplots
also mix models, storage sizes and device conditions.

## Coverage and missingness

{table(brand.reset_index())}

{table(top_models)}

{table(missing)}

Unknown seller type does not establish private ownership. Entirely missing fields
such as year, box and warranty cannot currently help a model. Missing RAM/storage
can reflect missing source properties or an unsupported memory format; inspect
raw_properties before deciding to impute. Candidate status does not establish that
every device is a genuine, working smartphone.

## Duplicate and evaluation checks

{potential_duplicates} rows share brand, model, storage, condition, price and normalized
nonempty description with another row. Review these before splitting: repeated ads
could otherwise appear in both training and validation. They were not removed.

This is a convenience sample from a live feed. Model coverage and seller promotions
can bias it. Do not interpret this sample as the overall Azerbaijani phone market.
This exploratory report examines all candidates, including the exploratory holdout. Before modeling, define device scope, review suspicious records and split
by duplicate/device groups where possible. Keep future test data out of tuning.

## Next modeling decisions

Train on both used and new listings with condition as a feature. Select models by
used-only MAE in grouped cross-validation on the training partition. Report used
and new MAE and signed error separately on the frozen holdout. Compare unweighted
and used-weighted training against a median baseline. Never select a model from
mixed MAE or tune against the holdout. Expand
data coverage before claiming reliable predictions across all brands and models.
"""
    (output / "eda.md").write_text(report, encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/candidates.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/eda"))
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
