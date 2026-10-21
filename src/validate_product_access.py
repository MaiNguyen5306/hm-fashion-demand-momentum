"""Check real product access outside the compact example export."""

import json
from pathlib import Path

import pandas as pd

from product_data import ProductDataStore


ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / "outputs/product_access_validation.json"
    destination.write_text(json.dumps({"passed": False, "status": "running"}) + "\n")
    store = ProductDataStore()
    profiles = store.products()
    exported = pd.read_parquet(ROOT / "dashboard/data/product_profiles.parquet")
    sample = set(exported.loc[exported.has_daily_curve, "article_id"])
    outside = profiles.loc[~profiles.article_id.isin(sample)]
    if outside.empty:
        raise ValueError("No products outside the sample available for full-history access check.")
    selected = outside.iloc[sorted({0, len(outside)//2, len(outside)-1})]
    checks = []
    for row in selected.itertuples():
        history = store.history(row.article_id)
        if len(history) != row.observed_lifespan_days or history.daily_units.sum() != row.total_units:
            raise ValueError(f"History does not reconcile for {row.article_id}")
        if history.cumulative_units.iloc[-1] != row.total_units or abs(history.cumulative_share_pct.iloc[-1]-100) > 1e-9:
            raise ValueError(f"Invalid accumulation for {row.article_id}")
        start = str(history.date.iloc[len(history)//2])[:10]
        actual = store.history(row.article_id, start_date=start)
        expected = history.loc[history.date.ge(start)].reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, expected)
        checks.append({"article_id": row.article_id, "rows": len(history),
                       "date_filter_preserves_history": True})
    destination.write_text(json.dumps({"passed": True, "eligible_products": len(profiles),
                                       "outside_sample_checks": checks}, indent=2) + "\n")
    print(f"Validated {len(profiles)} product metadata rows and {len(checks)} non-sample histories.")


if __name__ == "__main__":
    main()
