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

if int(fact_quality.loc[0, "panel_rows"]) != 8_788_910 or int(fact_quality.loc[0, "total_units"]) != 31_788_324:
    raise ValueError("Daily fact count or unit reconciliation failed.")
for field in ["missing_keys", "invalid_units"]:
    if int(fact_quality.loc[0, field]) != 0:
        raise ValueError(f"Fact table failed check: {field}")
if int(duplicate_grain.loc[0, "duplicate_groups"]) != 0:
    raise ValueError("Duplicate fact keys detected.")
if int(dimension_coverage.loc[0, "unmatched_articles"]) != 0 or int(dimension_coverage.loc[0, "purchased_articles"]) != 104_547:
    raise ValueError("Purchased-article count or dimension coverage failed.")
dimension_rows, unique_articles = con.execute(
    f"SELECT COUNT(*), COUNT(DISTINCT article_id) FROM read_parquet('{article_dim}')"
).fetchone()
if dimension_rows != 105_542 or unique_articles != dimension_rows:
    raise ValueError("Article dimension keys are not unique or catalog count differs.")

con.close()

print("\nProcessed data validation complete.")
