from pathlib import Path
import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DAILY_PANEL = (
    PROJECT_ROOT / "data" / "processed" / "daily_article_sales.parquet"
)

ARTICLE_DIM = (
    PROJECT_ROOT / "data" / "processed" / "article_dimension.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

daily_panel = DAILY_PANEL.as_posix()
article_dim = ARTICLE_DIM.as_posix()

con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")


print("\nH&M BUSINESS EDA SUMMARY")
print("=" * 50)


# --------------------------------------------------
# 1. Overall demand profile
# --------------------------------------------------

overall = con.execute(
    f"""
    SELECT
        MIN(date) AS start_date,
        MAX(date) AS end_date,
        COUNT(DISTINCT date) AS calendar_days,
        COUNT(DISTINCT article_id) AS purchased_articles,
        SUM(units_sold) AS total_units,
        AVG(units_sold) AS avg_units_per_article_day_channel
    FROM read_parquet('{daily_panel}')
    """
).fetchdf()

overall.to_csv(
    OUTPUT_DIR / "overall_summary.csv",
    index=False
)

print("\nOVERALL")
print(overall.to_string(index=False))


# --------------------------------------------------
# 2. Sales channel mix
# --------------------------------------------------

channel_summary = con.execute(
    f"""
    SELECT
        sales_channel_id,
        SUM(units_sold) AS units_sold,
        ROUND(
            100.0 * SUM(units_sold)
            / SUM(SUM(units_sold)) OVER (),
            2
        ) AS unit_share_pct,
        COUNT(DISTINCT article_id) AS active_articles
    FROM read_parquet('{daily_panel}')
    GROUP BY sales_channel_id
    ORDER BY units_sold DESC
    """
).fetchdf()

channel_summary.to_csv(
    OUTPUT_DIR / "channel_summary.csv",
    index=False
)

print("\nSALES CHANNELS")
print(channel_summary.to_string(index=False))


# --------------------------------------------------
# 3. Garment group performance
# --------------------------------------------------

garment_summary = con.execute(
    f"""
    SELECT
        d.garment_group_name,
        SUM(f.units_sold) AS units_sold,
        COUNT(DISTINCT f.article_id) AS purchased_articles,
        COUNT(DISTINCT f.date) AS active_days,
        ROUND(
            100.0 * SUM(f.units_sold)
            / SUM(SUM(f.units_sold)) OVER (),
            2
        ) AS unit_share_pct
    FROM read_parquet('{daily_panel}') AS f

    INNER JOIN read_parquet('{article_dim}') AS d
        ON f.article_id = d.article_id

    GROUP BY d.garment_group_name
    ORDER BY units_sold DESC
    """
).fetchdf()

garment_summary.to_csv(
    OUTPUT_DIR / "garment_group_summary.csv",
    index=False
)

print("\nTOP 10 GARMENT GROUPS")
print(garment_summary.head(10).to_string(index=False))


# --------------------------------------------------
# 4. Monthly demand
# --------------------------------------------------

monthly_summary = con.execute(
    f"""
    SELECT
        DATE_TRUNC('month', date) AS month,
        SUM(units_sold) AS units_sold,
        COUNT(DISTINCT article_id) AS active_articles
    FROM read_parquet('{daily_panel}')
    GROUP BY month
    ORDER BY month
    """
).fetchdf()

monthly_summary.to_csv(
    OUTPUT_DIR / "monthly_demand.csv",
    index=False
)

print("\nMONTHLY DEMAND")
print(monthly_summary.to_string(index=False))


# --------------------------------------------------
# 5. Reconciliation
# --------------------------------------------------

expected_units = 31_788_324

channel_units = int(channel_summary["units_sold"].sum())
garment_units = int(garment_summary["units_sold"].sum())
monthly_units = int(monthly_summary["units_sold"].sum())

print("\nRECONCILIATION")
print("-" * 50)

print(f"Expected raw units:  {expected_units:,}")
print(f"Channel total:       {channel_units:,}")
print(f"Garment total:       {garment_units:,}")
print(f"Monthly total:       {monthly_units:,}")

assert channel_units == expected_units
assert garment_units == expected_units
assert monthly_units == expected_units

print("\nAll EDA summaries reconcile to raw transaction volume.")

con.close()

print("\nEDA summary complete.")