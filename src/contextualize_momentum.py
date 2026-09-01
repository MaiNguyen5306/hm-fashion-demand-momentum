from pathlib import Path
import duckdb


# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

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

CONTEXTUAL_METRICS = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "contextual_momentum_metrics.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


momentum_metrics = MOMENTUM_METRICS.as_posix()
article_summary = ARTICLE_SUMMARY.as_posix()
article_dim = ARTICLE_DIM.as_posix()
lifecycle_path = LIFECYCLE_PATH.as_posix()
contextual_metrics = CONTEXTUAL_METRICS.as_posix()


# --------------------------------------------------
# DuckDB setup
# --------------------------------------------------

con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")
con.execute("SET preserve_insertion_order = false")


print("\nCONTEXTUALIZING H&M DEMAND MOMENTUM")
print("=" * 60)


# --------------------------------------------------
# 1. Create contextual article-day metrics
# --------------------------------------------------

print("\nCreating contextual article-day momentum metrics...")


con.execute(
    f"""
    COPY (

        WITH scaled AS (

            SELECT
                m.*,

                s.peak_smoothed_demand,

                l.avg_units_per_active_day,

                -- -----------------------------------
                -- Relative to article's observed peak
                -- Retained as a descriptive metric,
                -- but NOT our main normalized metric.
                -- -----------------------------------

                CASE
                    WHEN m.valid_momentum_day = 1
                     AND s.peak_smoothed_demand > 0

                    THEN
                        100.0
                        * m.demand_velocity
                        / s.peak_smoothed_demand

                    ELSE NULL
                END AS velocity_pct_of_peak,


                CASE
                    WHEN m.valid_momentum_day = 1
                     AND s.peak_smoothed_demand > 0

                    THEN
                        100.0
                        * m.demand_acceleration
                        / s.peak_smoothed_demand

                    ELSE NULL
                END AS acceleration_pct_of_peak,


                -- -----------------------------------
                -- Main scale-adjusted momentum metric
                -- -----------------------------------

                CASE
                    WHEN m.valid_momentum_day = 1
                     AND l.avg_units_per_active_day > 0

                    THEN
                        100.0
                        * m.demand_velocity
                        / l.avg_units_per_active_day

                    ELSE NULL
                END AS velocity_pct_of_typical_day,


                CASE
                    WHEN m.valid_momentum_day = 1
                     AND l.avg_units_per_active_day > 0

                    THEN
                        100.0
                        * m.demand_acceleration
                        / l.avg_units_per_active_day

                    ELSE NULL
                END AS acceleration_pct_of_typical_day


            FROM read_parquet('{momentum_metrics}') AS m


            INNER JOIN read_parquet('{article_summary}') AS s
                ON m.article_id = s.article_id


            INNER JOIN read_parquet('{lifecycle_path}') AS l
                ON m.article_id = l.article_id
        ),


        -- --------------------------------------------------
        -- Rank only observations where momentum is valid.
        -- This prevents lifecycle-edge NULL rows from
        -- affecting same-day percentile calculations.
        -- --------------------------------------------------

        valid_ranked AS (

            SELECT
                article_id,
                date,

                100.0 * PERCENT_RANK() OVER (
                    PARTITION BY date
                    ORDER BY demand_velocity
                ) AS daily_velocity_percentile,


                100.0 * PERCENT_RANK() OVER (
                    PARTITION BY date
                    ORDER BY velocity_pct_of_typical_day
                ) AS daily_relative_velocity_percentile


            FROM scaled

            WHERE valid_momentum_day = 1
        )


        SELECT
            s.*,

            r.daily_velocity_percentile,
            r.daily_relative_velocity_percentile


        FROM scaled AS s


        LEFT JOIN valid_ranked AS r
            ON s.article_id = r.article_id
           AND s.date = r.date
    )


    TO '{contextual_metrics}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)


print("Contextual momentum metrics created.")


# --------------------------------------------------
# 2. Catalog-wide daily momentum
# --------------------------------------------------

catalog_daily = con.execute(
    f"""
    WITH daily AS (

        SELECT
            date,

            SUM(daily_units)
                AS catalog_units,

            COUNT(DISTINCT article_id)
                AS observed_articles,


            SUM(
                CASE
                    WHEN valid_momentum_day = 1
                    THEN 1
                    ELSE 0
                END
            ) AS valid_momentum_articles,


            SUM(
                CASE
                    WHEN valid_momentum_day = 1
                     AND demand_velocity > 0
                    THEN 1
                    ELSE 0
                END
            ) AS positive_velocity_articles,


            AVG(
                CASE
                    WHEN valid_momentum_day = 1
                    THEN demand_velocity
                END
            ) AS avg_article_velocity,


            MEDIAN(
                CASE
                    WHEN valid_momentum_day = 1
                    THEN demand_velocity
                END
            ) AS median_article_velocity,


            AVG(
                CASE
                    WHEN valid_momentum_day = 1
                    THEN velocity_pct_of_typical_day
                END
            ) AS avg_relative_velocity_pct


        FROM read_parquet('{contextual_metrics}')

        GROUP BY date
    )


    SELECT
        *,

        ROUND(
            100.0
            * positive_velocity_articles
            / NULLIF(valid_momentum_articles, 0),
            2
        ) AS positive_velocity_share_pct


    FROM daily

    ORDER BY date
    """
).fetchdf()


catalog_daily.to_csv(
    OUTPUT_DIR / "catalog_daily_momentum.csv",
    index=False
)


print("\nCATALOG DAILY MOMENTUM SAMPLE")
print(catalog_daily.head(10).to_string(index=False))


# --------------------------------------------------
# 3. Highest scale-adjusted momentum observations
# --------------------------------------------------

top_relative = con.execute(
    f"""
    SELECT
        c.article_id,

        d.prod_name,
        d.product_type_name,
        d.garment_group_name,

        c.date,

        c.daily_units,

        ROUND(c.units_ma7, 2)
            AS units_ma7,

        ROUND(c.avg_units_per_active_day, 2)
            AS avg_units_per_active_day,

        ROUND(c.peak_smoothed_demand, 2)
            AS peak_smoothed_demand,

        ROUND(c.demand_velocity, 2)
            AS demand_velocity,

        ROUND(c.velocity_pct_of_typical_day, 2)
            AS velocity_pct_of_typical_day,

        ROUND(c.velocity_pct_of_peak, 2)
            AS velocity_pct_of_peak,

        ROUND(c.daily_velocity_percentile, 2)
            AS daily_velocity_percentile,

        ROUND(c.daily_relative_velocity_percentile, 2)
            AS daily_relative_velocity_percentile


    FROM read_parquet('{contextual_metrics}') AS c


    INNER JOIN read_parquet('{article_dim}') AS d
        ON c.article_id = d.article_id


    WHERE c.valid_momentum_day = 1


    ORDER BY
        c.velocity_pct_of_typical_day DESC


    LIMIT 25
    """
).fetchdf()


top_relative.to_csv(
    OUTPUT_DIR / "top_relative_momentum_observations.csv",
    index=False
)


print("\nTOP 25 SCALE-ADJUSTED MOMENTUM OBSERVATIONS")
print(top_relative.to_string(index=False))


# --------------------------------------------------
# 4. Highest absolute momentum with context
# --------------------------------------------------

top_absolute = con.execute(
    f"""
    SELECT
        c.article_id,

        d.prod_name,
        d.product_type_name,
        d.garment_group_name,

        c.date,

        ROUND(c.units_ma7, 2)
            AS units_ma7,

        ROUND(c.avg_units_per_active_day, 2)
            AS avg_units_per_active_day,

        ROUND(c.demand_velocity, 2)
            AS demand_velocity,

        ROUND(c.velocity_pct_of_typical_day, 2)
            AS velocity_pct_of_typical_day,

        ROUND(c.velocity_pct_of_peak, 2)
            AS velocity_pct_of_peak,

        ROUND(c.daily_velocity_percentile, 2)
            AS daily_velocity_percentile,

        ROUND(c.daily_relative_velocity_percentile, 2)
            AS daily_relative_velocity_percentile


    FROM read_parquet('{contextual_metrics}') AS c


    INNER JOIN read_parquet('{article_dim}') AS d
        ON c.article_id = d.article_id


    WHERE c.valid_momentum_day = 1


    ORDER BY
        c.demand_velocity DESC


    LIMIT 25
    """
).fetchdf()


top_absolute.to_csv(
    OUTPUT_DIR / "top_absolute_momentum_with_context.csv",
    index=False
)


print("\nTOP 25 ABSOLUTE MOMENTUM OBSERVATIONS")
print(top_absolute.to_string(index=False))


# --------------------------------------------------
# 5. Validation
# --------------------------------------------------

validation = con.execute(
    f"""
    SELECT
        COUNT(*) AS panel_rows,

        COUNT(DISTINCT article_id)
            AS articles,

        SUM(daily_units)
            AS total_units,


        SUM(
            CASE
                WHEN valid_momentum_day = 1
                 AND velocity_pct_of_typical_day IS NULL
                THEN 1
                ELSE 0
            END
        ) AS missing_relative_velocity,


        SUM(
            CASE
                WHEN valid_momentum_day = 1
                 AND daily_velocity_percentile IS NULL
                THEN 1
                ELSE 0
            END
        ) AS missing_velocity_percentile,


        SUM(
            CASE
                WHEN valid_momentum_day = 1
                 AND daily_relative_velocity_percentile IS NULL
                THEN 1
                ELSE 0
            END
        ) AS missing_relative_percentile,


        MIN(
            CASE
                WHEN valid_momentum_day = 1
                THEN daily_velocity_percentile
            END
        ) AS min_velocity_percentile,


        MAX(
            CASE
                WHEN valid_momentum_day = 1
                THEN daily_velocity_percentile
            END
        ) AS max_velocity_percentile,


        MIN(
            CASE
                WHEN valid_momentum_day = 1
                THEN daily_relative_velocity_percentile
            END
        ) AS min_relative_percentile,


        MAX(
            CASE
                WHEN valid_momentum_day = 1
                THEN daily_relative_velocity_percentile
            END
        ) AS max_relative_percentile


    FROM read_parquet('{contextual_metrics}')
    """
).fetchdf()


validation.to_csv(
    OUTPUT_DIR / "contextual_momentum_validation.csv",
    index=False
)


print("\nVALIDATION")
print(validation.to_string(index=False))


con.close()

print("\nContextual momentum analysis complete.")