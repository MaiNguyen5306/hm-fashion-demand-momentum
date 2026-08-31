from pathlib import Path
import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DAILY_PANEL = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "daily_article_sales.parquet"
)

LIFECYCLE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "article_lifecycle.parquet"
)

MOMENTUM_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "momentum_daily_panel.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

daily_panel = DAILY_PANEL.as_posix()
lifecycle_path = LIFECYCLE_PATH.as_posix()
momentum_path = MOMENTUM_PATH.as_posix()


con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")
con.execute("SET preserve_insertion_order = false")


print("\nBUILDING H&M MOMENTUM PANEL")
print("=" * 55)


# --------------------------------------------------
# Build dense daily panel
# --------------------------------------------------

print("\nCreating continuous daily demand histories...")
print("Zero-sale dates will be inserted explicitly.")


con.execute(
    f"""
    COPY (
        WITH eligible_articles AS (

            SELECT
                article_id,
                first_sale_date,
                last_sale_date,
                observed_lifespan_days,
                left_censored,
                right_censored

            FROM read_parquet('{lifecycle_path}')

            WHERE active_sales_days >= 30
              AND total_units >= 100
        ),

        daily_demand AS (

            SELECT
                date,
                article_id,
                SUM(units_sold) AS daily_units

            FROM read_parquet('{daily_panel}')

            GROUP BY
                date,
                article_id
        ),

        calendar_grid AS (

            SELECT
                e.article_id,
                CAST(g.generated_date AS DATE) AS date,
                e.first_sale_date,
                e.last_sale_date,
                e.observed_lifespan_days,
                e.left_censored,
                e.right_censored

            FROM eligible_articles AS e

            CROSS JOIN LATERAL generate_series(
                e.first_sale_date,
                e.last_sale_date,
                INTERVAL 1 DAY
            ) AS g(generated_date)
        ),

        zero_filled AS (

            SELECT
                c.article_id,
                c.date,

                COALESCE(d.daily_units, 0)
                    AS daily_units,

                c.first_sale_date,
                c.last_sale_date,
                c.observed_lifespan_days,
                c.left_censored,
                c.right_censored,

                CASE
                    WHEN c.left_censored = 0
                     AND c.right_censored = 0
                    THEN 1
                    ELSE 0
                END AS complete_lifecycle

            FROM calendar_grid AS c

            LEFT JOIN daily_demand AS d
                ON c.article_id = d.article_id
               AND c.date = d.date
        )

        SELECT
            article_id,
            date,
            daily_units,

            AVG(daily_units) OVER (
                PARTITION BY article_id
                ORDER BY date
                ROWS BETWEEN 3 PRECEDING
                         AND 3 FOLLOWING
            ) AS units_ma7,

            COUNT(*) OVER (
                PARTITION BY article_id
                ORDER BY date
                ROWS BETWEEN 3 PRECEDING
                         AND 3 FOLLOWING
            ) AS ma7_window_days,

            first_sale_date,
            last_sale_date,
            observed_lifespan_days,
            left_censored,
            right_censored,
            complete_lifecycle

        FROM zero_filled
    )

    TO '{momentum_path}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)


print("Momentum panel created.")


# --------------------------------------------------
# Validation
# --------------------------------------------------

summary = con.execute(
    f"""
    SELECT
        COUNT(*) AS panel_rows,
        COUNT(DISTINCT article_id) AS articles,
        MIN(date) AS start_date,
        MAX(date) AS end_date,

        SUM(daily_units) AS total_units,

        SUM(
            CASE
                WHEN daily_units = 0
                THEN 1
                ELSE 0
            END
        ) AS zero_sales_days,

        ROUND(
            100.0 * SUM(
                CASE
                    WHEN daily_units = 0
                    THEN 1
                    ELSE 0
                END
            ) / COUNT(*),
            2
        ) AS zero_sales_day_pct,

        COUNT(
            DISTINCT CASE
                WHEN complete_lifecycle = 1
                THEN article_id
            END
        ) AS complete_lifecycle_articles

    FROM read_parquet('{momentum_path}')
    """
).fetchdf()


summary.to_csv(
    OUTPUT_DIR / "momentum_panel_summary.csv",
    index=False
)


print("\nMOMENTUM PANEL SUMMARY")
print(summary.to_string(index=False))


# --------------------------------------------------
# Grain validation
# --------------------------------------------------

duplicate_check = con.execute(
    f"""
    SELECT COUNT(*) AS duplicate_groups

    FROM (
        SELECT
            article_id,
            date,
            COUNT(*) AS row_count

        FROM read_parquet('{momentum_path}')

        GROUP BY
            article_id,
            date

        HAVING COUNT(*) > 1
    )
    """
).fetchdf()


print("\nDUPLICATE ARTICLE-DATE CHECK")
print(duplicate_check.to_string(index=False))


# --------------------------------------------------
# Continuity validation
# --------------------------------------------------

continuity_check = con.execute(
    f"""
    SELECT
        COUNT(*) AS articles_with_date_gaps

    FROM (
        SELECT
            article_id,
            COUNT(*) AS actual_days,
            MAX(observed_lifespan_days) AS expected_days

        FROM read_parquet('{momentum_path}')

        GROUP BY article_id

        HAVING COUNT(*) != MAX(observed_lifespan_days)
    )
    """
).fetchdf()


print("\nDATE CONTINUITY CHECK")
print(continuity_check.to_string(index=False))


con.close()

print("\nMomentum panel build complete.")