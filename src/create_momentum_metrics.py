from pathlib import Path
import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MOMENTUM_PANEL = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "momentum_daily_panel.parquet"
)

MOMENTUM_METRICS = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "momentum_metrics.parquet"
)

ARTICLE_SUMMARY = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "article_momentum_summary.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

momentum_panel = MOMENTUM_PANEL.as_posix()
momentum_metrics = MOMENTUM_METRICS.as_posix()
article_summary = ARTICLE_SUMMARY.as_posix()


con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")
con.execute("SET preserve_insertion_order = false")


print("\nBUILDING H&M DEMAND MOMENTUM METRICS")
print("=" * 55)


# --------------------------------------------------
# 1. Daily velocity and acceleration
# --------------------------------------------------

print("\nCalculating finite-difference momentum metrics...")


con.execute(
    f"""
    COPY (
        WITH neighbors AS (

            SELECT
                *,

                LAG(units_ma7) OVER (
                    PARTITION BY article_id
                    ORDER BY date
                ) AS prev_ma7,

                LEAD(units_ma7) OVER (
                    PARTITION BY article_id
                    ORDER BY date
                ) AS next_ma7,

                LAG(ma7_window_days) OVER (
                    PARTITION BY article_id
                    ORDER BY date
                ) AS prev_window_days,

                LEAD(ma7_window_days) OVER (
                    PARTITION BY article_id
                    ORDER BY date
                ) AS next_window_days

            FROM read_parquet('{momentum_panel}')
        ),

        calculated AS (

            SELECT
                article_id,
                date,
                daily_units,
                units_ma7,
                ma7_window_days,

                first_sale_date,
                last_sale_date,
                observed_lifespan_days,
                left_censored,
                right_censored,
                complete_lifecycle,

                CASE
                    WHEN ma7_window_days = 7
                     AND prev_window_days = 7
                     AND next_window_days = 7
                    THEN 1
                    ELSE 0
                END AS valid_momentum_day,

                CASE
                    WHEN ma7_window_days = 7
                     AND prev_window_days = 7
                     AND next_window_days = 7

                    THEN (next_ma7 - prev_ma7) / 2.0
                    ELSE NULL
                END AS demand_velocity,

                CASE
                    WHEN ma7_window_days = 7
                     AND prev_window_days = 7
                     AND next_window_days = 7

                    THEN next_ma7
                       - (2.0 * units_ma7)
                       + prev_ma7

                    ELSE NULL
                END AS demand_acceleration

            FROM neighbors
        )

        SELECT *
        FROM calculated
    )

    TO '{momentum_metrics}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)


print("Daily momentum metrics created.")


# --------------------------------------------------
# 2. Article-level momentum summary
# --------------------------------------------------

print("\nCreating article momentum summary...")


con.execute(
    f"""
    COPY (
        SELECT
            article_id,

            COUNT(*) AS observed_days,

            SUM(valid_momentum_day)
                AS valid_momentum_days,

            SUM(daily_units)
                AS total_units,

            MAX(units_ma7)
                AS peak_smoothed_demand,

            ARG_MAX(date, units_ma7)
                AS peak_smoothed_demand_date,

            MAX(demand_velocity)
                AS max_positive_velocity,

            ARG_MAX(date, demand_velocity)
                AS max_velocity_date,

            MIN(demand_velocity)
                AS max_negative_velocity,

            ARG_MIN(date, demand_velocity)
                AS max_negative_velocity_date,

            MAX(demand_acceleration)
                AS max_positive_acceleration,

            ARG_MAX(date, demand_acceleration)
                AS max_acceleration_date,

            MIN(demand_acceleration)
                AS max_negative_acceleration,

            ARG_MIN(date, demand_acceleration)
                AS max_negative_acceleration_date,

            MAX(complete_lifecycle)
                AS complete_lifecycle

        FROM read_parquet('{momentum_metrics}')

        GROUP BY article_id
    )

    TO '{article_summary}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)


print("Article momentum summary created.")


# --------------------------------------------------
# 3. Validation summary
# --------------------------------------------------

validation = con.execute(
    f"""
    SELECT
        COUNT(*) AS panel_rows,

        COUNT(DISTINCT article_id)
            AS articles,

        SUM(daily_units)
            AS total_units,

        SUM(valid_momentum_day)
            AS valid_momentum_rows,

        ROUND(
            100.0 * SUM(valid_momentum_day)
            / COUNT(*),
            2
        ) AS valid_momentum_pct,

        SUM(
            CASE
                WHEN valid_momentum_day = 1
                 AND (
                     demand_velocity IS NULL
                     OR demand_acceleration IS NULL
                 )
                THEN 1
                ELSE 0
            END
        ) AS invalid_metric_rows,

        SUM(
            CASE
                WHEN valid_momentum_day = 0
                 AND (
                     demand_velocity IS NOT NULL
                     OR demand_acceleration IS NOT NULL
                 )
                THEN 1
                ELSE 0
            END
        ) AS metrics_outside_valid_window

    FROM read_parquet('{momentum_metrics}')
    """
).fetchdf()


validation.to_csv(
    OUTPUT_DIR / "momentum_metrics_validation.csv",
    index=False
)


print("\nMOMENTUM METRICS VALIDATION")
print(validation.to_string(index=False))


# --------------------------------------------------
# 4. Distribution summary
# --------------------------------------------------

distribution = con.execute(
    f"""
    SELECT

        PERCENTILE_CONT(0.05)
            WITHIN GROUP (ORDER BY demand_velocity)
            AS velocity_p05,

        PERCENTILE_CONT(0.25)
            WITHIN GROUP (ORDER BY demand_velocity)
            AS velocity_p25,

        MEDIAN(demand_velocity)
            AS velocity_median,

        PERCENTILE_CONT(0.75)
            WITHIN GROUP (ORDER BY demand_velocity)
            AS velocity_p75,

        PERCENTILE_CONT(0.95)
            WITHIN GROUP (ORDER BY demand_velocity)
            AS velocity_p95,

        PERCENTILE_CONT(0.05)
            WITHIN GROUP (ORDER BY demand_acceleration)
            AS acceleration_p05,

        PERCENTILE_CONT(0.25)
            WITHIN GROUP (ORDER BY demand_acceleration)
            AS acceleration_p25,

        MEDIAN(demand_acceleration)
            AS acceleration_median,

        PERCENTILE_CONT(0.75)
            WITHIN GROUP (ORDER BY demand_acceleration)
            AS acceleration_p75,

        PERCENTILE_CONT(0.95)
            WITHIN GROUP (ORDER BY demand_acceleration)
            AS acceleration_p95

    FROM read_parquet('{momentum_metrics}')

    WHERE valid_momentum_day = 1
    """
).fetchdf()


distribution.to_csv(
    OUTPUT_DIR / "momentum_distribution_summary.csv",
    index=False
)


print("\nMOMENTUM DISTRIBUTIONS")
print(distribution.to_string(index=False))


# --------------------------------------------------
# 5. Highest-momentum articles
# --------------------------------------------------

top_momentum = con.execute(
    f"""
    SELECT
        article_id,
        total_units,
        peak_smoothed_demand,
        peak_smoothed_demand_date,

        ROUND(max_positive_velocity, 2)
            AS max_positive_velocity,

        max_velocity_date,

        ROUND(max_positive_acceleration, 2)
            AS max_positive_acceleration,

        max_acceleration_date,

        complete_lifecycle

    FROM read_parquet('{article_summary}')

    ORDER BY max_positive_velocity DESC

    LIMIT 15
    """
).fetchdf()


top_momentum.to_csv(
    OUTPUT_DIR / "top_momentum_articles.csv",
    index=False
)


print("\nTOP 15 ARTICLES BY POSITIVE VELOCITY")
print(top_momentum.to_string(index=False))


con.close()

print("\nMomentum metric build complete.")