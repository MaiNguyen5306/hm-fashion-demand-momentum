"""Export verified, size-limited dashboard data without changing analytical inputs."""

import argparse
import json
from pathlib import Path
import tempfile

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def export(processed_dir, output_dir, summary_dir, per_profile=5, max_mb=25):
    if per_profile < 1 or max_mb <= 0:
        raise ValueError("Sample size and size budget must be positive.")
    required = ["product_profiles.parquet", "contextual_momentum_metrics.parquet"]
    missing = [str(processed_dir / name) for name in required
               if not (processed_dir / name).is_file()]
    if missing:
        raise FileNotFoundError("Restore processed inputs before exporting:\n" + "\n".join(missing))
    output_dir = output_dir.resolve()
    if output_dir == processed_dir.resolve() or output_dir == summary_dir.resolve():
        raise ValueError("Export directory must be separate from input directories.")

    with duckdb.connect() as con:
        con.execute("SET threads = 2")
        con.execute("SET memory_limit = '3GB'")
        con.read_parquet(str(processed_dir / required[0])).create_view("profiles")
        con.read_parquet(str(processed_dir / required[1])).create_view("momentum")
        profiles = con.sql("SELECT * FROM profiles ORDER BY article_id").df()
        if profiles.empty or profiles.article_id.isna().any() or profiles.article_id.duplicated().any():
            raise ValueError("Product profiles must have unique, non-null article IDs.")
        if profiles[["lifecycle_profile", "momentum_tier"]].isna().any().any():
            raise ValueError("Missing product classification.")
        expected = pd.read_csv(summary_dir / "product_profile_validation.csv").iloc[0]
        if len(profiles) != int(expected.articles) or profiles.total_units.sum() != expected.total_units:
            raise ValueError("Profile population does not reconcile to saved validation.")
        curves = con.sql(f"""
            WITH selected AS (
                SELECT article_id FROM profiles
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY lifecycle_profile
                    ORDER BY total_units DESC, article_id
                ) <= {int(per_profile)}
            )
            SELECT m.article_id, m.date, m.daily_units, m.units_ma7,
                   m.valid_momentum_day, m.demand_velocity, m.demand_acceleration,
                   m.velocity_pct_of_typical_day,
                   m.daily_velocity_percentile, m.daily_relative_velocity_percentile,
                   SUM(m.daily_units) OVER (
                       PARTITION BY m.article_id ORDER BY m.date
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                   ) AS cumulative_units
            FROM momentum m INNER JOIN selected s USING (article_id)
            ORDER BY m.article_id, m.date
        """).df()
        selected_profiles = profiles.sort_values(
            ["lifecycle_profile", "total_units", "article_id"], ascending=[True, False, True]
        ).groupby("lifecycle_profile", sort=False).head(per_profile)
        if set(curves.article_id) != set(selected_profiles.article_id):
            raise ValueError("Some selected products have no demand history.")
        if curves.duplicated(["article_id", "date"]).any() or curves.daily_units.isna().any() or (curves.daily_units < 0).any():
            raise ValueError("Invalid article-day grain or daily demand.")
        curves["date"] = pd.to_datetime(curves.date)
        if curves.groupby("article_id").date.diff().dropna().ne(pd.Timedelta(days=1)).any():
            raise ValueError("Selected curves contain date gaps.")
        totals = curves.groupby("article_id").daily_units.sum()
        selected = selected_profiles.set_index("article_id").loc[totals.index]
        if not totals.eq(selected.total_units).all():
            raise ValueError("Selected curve units do not reconcile to profiles.")
        grouped = curves.groupby("article_id")
        if not grouped.size().eq(selected.observed_lifespan_days).all():
            raise ValueError("Selected curve lifespan does not reconcile to profiles.")
        if not grouped.date.min().eq(pd.to_datetime(selected.first_sale_date)).all() or not grouped.date.max().eq(pd.to_datetime(selected.last_sale_date)).all():
            raise ValueError("Selected curve endpoints do not match observed lifecycles.")
        metrics = ["demand_velocity", "demand_acceleration", "velocity_pct_of_typical_day",
                   "daily_velocity_percentile", "daily_relative_velocity_percentile"]
        valid = curves.valid_momentum_day.eq(1)
        if curves.loc[valid, metrics].isna().any().any() or curves.loc[~valid, metrics].notna().any().any():
            raise ValueError("Momentum metrics violate valid-window rules.")
        curves["cumulative_share_pct"] = 100 * curves.cumulative_units / curves.article_id.map(totals)
        profiles["has_daily_curve"] = profiles.article_id.isin(totals.index)
        catalog = pd.read_csv(summary_dir / "catalog_daily_momentum.csv")
        if catalog.date.duplicated().any() or catalog.catalog_units.sum() != expected.total_units:
            raise ValueError("Catalog summary does not reconcile to eligible demand.")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir.parent) as temporary:
        staging = Path(temporary)
        profiles.to_parquet(staging / "product_profiles.parquet", index=False)
        curves.to_parquet(staging / "product_daily_curves.parquet", index=False)
        catalog.to_csv(staging / "catalog_daily_momentum.csv", index=False)
        sizes = {p.name: p.stat().st_size for p in staging.iterdir()}
        manifest = {
            "schema_version": 2,
            "eligible_articles": len(profiles),
            "eligible_units": int(profiles.total_units.sum()),
            "curve_articles": len(totals), "curve_rows": len(curves),
            "curve_selection": f"Top {per_profile} by total units per lifecycle profile; ties by article_id",
            "full_history_access": "src.product_data.ProductDataStore reads all eligible histories from local processed Parquet files",
            "peak_policy": "Earliest tied date; raw daily peak and smoothed peak are separate profile fields",
            "catalog_scope": "Momentum-eligible articles only",
            "momentum_interpretation": "Retrospective; centered smoothing and differences use future observations",
            "lifecycle_interpretation": "Complete means neither exact dataset boundary is touched; true lifecycle completeness is unknown",
            "file_bytes": sizes,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        if sum(p.stat().st_size for p in staging.iterdir()) > max_mb * 1024 * 1024:
            raise ValueError(f"Export exceeds {max_mb} MiB budget; existing export was not replaced.")
        output_dir.mkdir(parents=True, exist_ok=True)
        for path in staging.iterdir():
            path.replace(output_dir / path.name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dashboard/data")
    parser.add_argument("--summary-dir", type=Path, default=ROOT / "outputs")
    parser.add_argument("--per-profile", type=int, default=5)
    parser.add_argument("--max-mb", type=float, default=25)
    args = parser.parse_args()
    try:
        manifest = export(args.processed_dir, args.output_dir, args.summary_dir, args.per_profile, args.max_mb)
    except (FileNotFoundError, ValueError) as exc:
        parser.exit(1, f"Export stopped: {exc}\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
