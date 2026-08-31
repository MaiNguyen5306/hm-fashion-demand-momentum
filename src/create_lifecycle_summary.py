from pathlib import Path
import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DAILY_PANEL = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "daily_article_sales.parquet"
)

ARTICLE_DIM = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "article_dimension.parquet"
)

LIFECYCLE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "article_lifecycle.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

daily_panel = DAILY_PANEL.as_posix()
article_dim = ARTICLE_DIM.as_posix()
lifecycle_path = LIFECYCLE_PATH.as_posix()

con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")
con.execute("SET preserve_insertion_order = false")


print("\nBUILDING H&M ARTICLE LIFECYCLES")
print("=" * 50)


# --------------------------------------------------
# Build article-level daily demand first
# --------------------------------------------------

con.execute(
    f"""
    COPY (
        WITH daily_article AS (
            SELECT
                date,
                article_id,
                SUM(units_sold) AS daily_units
            FROM read_parquet('{daily_panel}')
            GROUP BY
                date,
                article_id
        ),

        lifecycle_base AS (
            SELECT
                article_id,
                MIN(date) AS first_sale_date,
                MAX(date) AS last_sale_date,
                DATE_DIFF(
                    'day',
                    MIN(date),
                    MAX(date)
                ) + 1 AS observed_lifespan_days,
                COUNT(*) AS active_sales_days,
                SUM(daily_units) AS total_units,
                MAX(daily_units) AS peak_daily_units,
                AVG(daily_units) AS avg_units_per_active_day
            FROM daily_article
            GROUP BY article_id
        ),

        peak_dates AS (
            SELECT
                article_id,
                date AS peak_date,
                daily_units AS peak_daily_units,
                ROW_NUMBER() OVER (
                    PARTITION BY article_id
                    ORDER BY daily_units DESC, date ASC
                ) AS peak_rank
            FROM daily_article
        )

        SELECT
            l.article_id,
            d.prod_name,
            d.product_type_name,
            d.product_group_name,
            d.garment_group_name,

            l.first_sale_date,
            l.last_sale_date,
            l.observed_lifespan_days,

            CASE
                WHEN l.first_sale_date = DATE '2018-09-20'
                THEN 1
                ELSE 0
            END AS left_censored,

            CASE
                WHEN l.last_sale_date = DATE '2020-09-22'
                THEN 1
                ELSE 0
            END AS right_censored,
            l.active_sales_days,
            l.total_units,
            l.peak_daily_units,
            p.peak_date,
            l.avg_units_per_active_day,

            ROUND(
                100.0 * l.active_sales_days
                / l.observed_lifespan_days,
                2
            ) AS active_day_rate_pct

        FROM lifecycle_base AS l

        INNER JOIN read_parquet('{article_dim}') AS d
            ON l.article_id = d.article_id

        INNER JOIN peak_dates AS p
            ON l.article_id = p.article_id
           AND p.peak_rank = 1
    )
    TO '{lifecycle_path}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)


print("Article lifecycle table created.")


# --------------------------------------------------
# Validate
# --------------------------------------------------

summary = con.execute(
    f"""
    SELECT
        COUNT(*) AS articles,
        MIN(first_sale_date) AS earliest_first_sale,
        MAX(last_sale_date) AS latest_last_sale,

        ROUND(
            AVG(observed_lifespan_days),
            1
        ) AS avg_observed_lifespan,

        MEDIAN(observed_lifespan_days)
            AS median_observed_lifespan,

        ROUND(
            AVG(active_sales_days),
            1
        ) AS avg_active_sales_days,

        MEDIAN(active_sales_days)
            AS median_active_sales_days,

        SUM(left_censored) AS left_censored_articles,
        SUM(right_censored) AS right_censored_articles,

        SUM(total_units) AS total_units

    FROM read_parquet('{lifecycle_path}')
    """
).fetchdf()


summary.to_csv(
    OUTPUT_DIR / "lifecycle_overview.csv",
    index=False
)


print("\nLIFECYCLE OVERVIEW")
print(summary.to_string(index=False))


# --------------------------------------------------
# Highest-volume articles
# --------------------------------------------------

top_articles = con.execute(
    f"""
    SELECT
        article_id,
        prod_name,
        garment_group_name,
        first_sale_date,
        last_sale_date,
        observed_lifespan_days,
        left_censored,
        right_censored,
        active_sales_days,
        total_units,
        peak_daily_units,
        peak_date,
        ROUND(avg_units_per_active_day, 2)
            AS avg_units_per_active_day,
        active_day_rate_pct

    FROM read_parquet('{lifecycle_path}')

    ORDER BY total_units DESC

    LIMIT 15
    """
).fetchdf()


top_articles.to_csv(
    OUTPUT_DIR / "top_article_lifecycles.csv",
    index=False
)


print("\nTOP 15 ARTICLES BY TOTAL UNITS")
print(top_articles.to_string(index=False))


con.close()

print("\nLifecycle build complete.")