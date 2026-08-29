from pathlib import Path
import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DAILY_PANEL = (
    PROJECT_ROOT / "data" / "processed" / "daily_article_sales.parquet"
)

ARTICLE_DIM = (
    PROJECT_ROOT / "data" / "processed" / "article_dimension.parquet"
)

daily_panel = DAILY_PANEL.as_posix()
article_dim = ARTICLE_DIM.as_posix()

con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")


print("\nH&M PROCESSED DATA VALIDATION")
print("=" * 50)


# --------------------------------------------------
# Fact table quality
# --------------------------------------------------

fact_quality = con.execute(
    f"""
    SELECT
        COUNT(*) AS panel_rows,

        SUM(
            CASE
                WHEN date IS NULL
                  OR article_id IS NULL
                  OR sales_channel_id IS NULL
                THEN 1
                ELSE 0
            END
        ) AS missing_keys,

        SUM(
            CASE
                WHEN units_sold <= 0
                THEN 1
                ELSE 0
            END
        ) AS invalid_units,

        SUM(units_sold) AS total_units

    FROM read_parquet('{daily_panel}')
    """
).fetchdf()

print("\nFACT TABLE QUALITY")
print(fact_quality.to_string(index=False))


# --------------------------------------------------
# Duplicate grain check
# --------------------------------------------------

duplicate_grain = con.execute(
    f"""
    SELECT COUNT(*) AS duplicate_groups
    FROM (
        SELECT
            date,
            article_id,
            sales_channel_id,
            COUNT(*) AS row_count

        FROM read_parquet('{daily_panel}')

        GROUP BY
            date,
            article_id,
            sales_channel_id

        HAVING COUNT(*) > 1
    )
    """
).fetchdf()

print("\nDUPLICATE GRAIN CHECK")
print(duplicate_grain.to_string(index=False))


# --------------------------------------------------
# Dimension coverage
# --------------------------------------------------

dimension_coverage = con.execute(
    f"""
    SELECT
        COUNT(DISTINCT f.article_id) AS purchased_articles,

        COUNT(
            DISTINCT CASE
                WHEN d.article_id IS NULL
                THEN f.article_id
            END
        ) AS unmatched_articles

    FROM read_parquet('{daily_panel}') AS f

    LEFT JOIN read_parquet('{article_dim}') AS d
        ON f.article_id = d.article_id
    """
).fetchdf()

print("\nDIMENSION COVERAGE")
print(dimension_coverage.to_string(index=False))


con.close()

print("\nProcessed data validation complete.")