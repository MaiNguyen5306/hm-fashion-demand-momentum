from pathlib import Path
import duckdb


# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MOMENTUM_PANEL = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "momentum_daily_panel.parquet"
)

ARTICLE_MOMENTUM = (
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

CUMULATIVE_DAILY = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "cumulative_lifecycle_daily.parquet"
)

LIFECYCLE_PERFORMANCE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "lifecycle_performance_summary.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


momentum_panel = MOMENTUM_PANEL.as_posix()
article_momentum = ARTICLE_MOMENTUM.as_posix()
article_dim = ARTICLE_DIM.as_posix()
cumulative_daily = CUMULATIVE_DAILY.as_posix()
lifecycle_performance = LIFECYCLE_PERFORMANCE.as_posix()


# --------------------------------------------------
# DuckDB setup
# --------------------------------------------------

con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")
con.execute("SET preserve_insertion_order = false")


print("\nBUILDING H&M CUMULATIVE LIFECYCLE METRICS")
print("=" * 60)


# --------------------------------------------------
# 1. Daily cumulative demand curves
# --------------------------------------------------

print("\nCreating cumulative article-demand curves...")


con.execute(
    f"""
    COPY (

        WITH totals AS (

            SELECT
                article_id,
                SUM(daily_units) AS lifecycle_total_units

            FROM read_parquet('{momentum_panel}')

            GROUP BY article_id
        )

        SELECT
            m.article_id,
            m.date,
            m.daily_units,
            m.units_ma7,

            t.lifecycle_total_units,

            SUM(m.daily_units) OVER (
                PARTITION BY m.article_id
                ORDER BY m.date
                ROWS BETWEEN UNBOUNDED PRECEDING
                         AND CURRENT ROW
            ) AS cumulative_units,

            100.0
            * SUM(m.daily_units) OVER (
                PARTITION BY m.article_id
                ORDER BY m.date
                ROWS BETWEEN UNBOUNDED PRECEDING
                         AND CURRENT ROW
            )
            / NULLIF(t.lifecycle_total_units, 0)
                AS cumulative_share_pct,

            SUM(m.daily_units) OVER (
                PARTITION BY m.article_id
                ORDER BY m.date
                ROWS BETWEEN 3 PRECEDING
                         AND 3 FOLLOWING
            ) AS rolling_7d_units,

            m.first_sale_date,
            m.last_sale_date,
            m.observed_lifespan_days,
            m.complete_lifecycle

        FROM read_parquet('{momentum_panel}') AS m

        INNER JOIN totals AS t
            ON m.article_id = t.article_id
    )

    TO '{cumulative_daily}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)


print("Cumulative daily lifecycle panel created.")


# --------------------------------------------------
# 2. Article-level cumulative performance
# --------------------------------------------------

print("\nCreating lifecycle performance summary...")


con.execute(
    f"""
    COPY (

        WITH milestone_dates AS (

            SELECT
                article_id,

                MIN(
                    CASE
                        WHEN cumulative_share_pct >= 50
                        THEN date
                    END
                ) AS cumulative_50_date,

                MIN(
                    CASE
                        WHEN cumulative_share_pct >= 80
                        THEN date
                    END
                ) AS cumulative_80_date,

                MAX(rolling_7d_units)
                    AS max_7d_units

            FROM read_parquet('{cumulative_daily}')

            GROUP BY article_id
        ),


        peak_split AS (

            SELECT
                c.article_id,

                SUM(
                    CASE
                        WHEN c.date < m.peak_smoothed_demand_date
                        THEN c.daily_units
                        ELSE 0
                    END
                ) AS pre_peak_units,

                SUM(
                    CASE
                        WHEN c.date = m.peak_smoothed_demand_date
                        THEN c.daily_units
                        ELSE 0
                    END
                ) AS peak_date_units,

                SUM(
                    CASE
                        WHEN c.date > m.peak_smoothed_demand_date
                        THEN c.daily_units
                        ELSE 0
                    END
                ) AS post_peak_units

            FROM read_parquet('{cumulative_daily}') AS c

            INNER JOIN read_parquet('{article_momentum}') AS m
                ON c.article_id = m.article_id

            GROUP BY c.article_id
        ),


        base AS (

            SELECT
                c.article_id,

                MIN(c.first_sale_date)
                    AS first_sale_date,

                MAX(c.last_sale_date)
                    AS last_sale_date,

                MAX(c.observed_lifespan_days)
                    AS observed_lifespan_days,

                MAX(c.complete_lifecycle)
                    AS complete_lifecycle,

                MAX(c.lifecycle_total_units)
                    AS total_units,

                m.cumulative_50_date,
                m.cumulative_80_date,
                m.max_7d_units,

                p.pre_peak_units,
                p.peak_date_units,
                p.post_peak_units

            FROM read_parquet('{cumulative_daily}') AS c

            INNER JOIN milestone_dates AS m
                ON c.article_id = m.article_id

            INNER JOIN peak_split AS p
                ON c.article_id = p.article_id

            GROUP BY
                c.article_id,
                m.cumulative_50_date,
                m.cumulative_80_date,
                m.max_7d_units,
                p.pre_peak_units,
                p.peak_date_units,
                p.post_peak_units
        )


        SELECT
            b.article_id,

            d.prod_name,
            d.product_type_name,
            d.garment_group_name,

            b.first_sale_date,
            b.last_sale_date,
            b.observed_lifespan_days,
            b.complete_lifecycle,

            b.total_units,

            b.cumulative_50_date,

            DATE_DIFF(
                'day',
                b.first_sale_date,
                b.cumulative_50_date
            ) AS days_to_50_pct,

            b.cumulative_80_date,

            DATE_DIFF(
                'day',
                b.first_sale_date,
                b.cumulative_80_date
            ) AS days_to_80_pct,

            b.pre_peak_units,
            b.peak_date_units,
            b.post_peak_units,

            ROUND(
                100.0
                * b.post_peak_units
                / NULLIF(b.total_units, 0),
                2
            ) AS post_peak_share_pct,

            b.max_7d_units,

            ROUND(
                100.0
                * b.max_7d_units
                / NULLIF(b.total_units, 0),
                2
            ) AS max_7d_demand_share_pct


        FROM base AS b

        INNER JOIN read_parquet('{article_dim}') AS d
            ON b.article_id = d.article_id
    )

    TO '{lifecycle_performance}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)


print("Lifecycle performance summary created.")


# --------------------------------------------------
# 3. Validation
# --------------------------------------------------

validation = con.execute(
    f"""
    SELECT
        COUNT(*) AS articles,

        SUM(total_units)
            AS total_units,

        SUM(
            CASE
                WHEN cumulative_50_date IS NULL
                THEN 1
                ELSE 0
            END
        ) AS missing_50_pct_date,

        SUM(
            CASE
                WHEN cumulative_80_date IS NULL
                THEN 1
                ELSE 0
            END
        ) AS missing_80_pct_date,

        SUM(
            CASE
                WHEN pre_peak_units
                   + peak_date_units
                   + post_peak_units
                   != total_units
                THEN 1
                ELSE 0
            END
        ) AS peak_split_mismatches,

        MIN(max_7d_demand_share_pct)
            AS min_7d_share,

        MAX(max_7d_demand_share_pct)
            AS max_7d_share

    FROM read_parquet('{lifecycle_performance}')
    """
).fetchdf()


validation.to_csv(
    OUTPUT_DIR / "cumulative_lifecycle_validation.csv",
    index=False
)


print("\nCUMULATIVE LIFECYCLE VALIDATION")
print(validation.to_string(index=False))


# --------------------------------------------------
# 4. Distribution summary
# --------------------------------------------------

distribution = con.execute(
    f"""
    SELECT

        MEDIAN(days_to_50_pct)
            AS median_days_to_50,

        PERCENTILE_CONT(0.25)
            WITHIN GROUP (ORDER BY days_to_50_pct)
            AS p25_days_to_50,

        PERCENTILE_CONT(0.75)
            WITHIN GROUP (ORDER BY days_to_50_pct)
            AS p75_days_to_50,


        MEDIAN(days_to_80_pct)
            AS median_days_to_80,

        PERCENTILE_CONT(0.25)
            WITHIN GROUP (ORDER BY days_to_80_pct)
            AS p25_days_to_80,

        PERCENTILE_CONT(0.75)
            WITHIN GROUP (ORDER BY days_to_80_pct)
            AS p75_days_to_80,


        MEDIAN(max_7d_demand_share_pct)
            AS median_max_7d_share,

        PERCENTILE_CONT(0.75)
            WITHIN GROUP (
                ORDER BY max_7d_demand_share_pct
            ) AS p75_max_7d_share,


        MEDIAN(post_peak_share_pct)
            AS median_post_peak_share

    FROM read_parquet('{lifecycle_performance}')

    WHERE complete_lifecycle = 1
    """
).fetchdf()


distribution.to_csv(
    OUTPUT_DIR / "cumulative_lifecycle_distribution.csv",
    index=False
)


print("\nCOMPLETE-LIFECYCLE DISTRIBUTIONS")
print(distribution.to_string(index=False))


# --------------------------------------------------
# 5. Most concentrated demand cycles
# --------------------------------------------------

concentrated = con.execute(
    f"""
    SELECT
        article_id,
        prod_name,
        product_type_name,
        garment_group_name,

        observed_lifespan_days,
        total_units,

        days_to_50_pct,
        days_to_80_pct,

        max_7d_units,
        max_7d_demand_share_pct,

        post_peak_share_pct

    FROM read_parquet('{lifecycle_performance}')

    WHERE complete_lifecycle = 1

    ORDER BY max_7d_demand_share_pct DESC

    LIMIT 20
    """
).fetchdf()


concentrated.to_csv(
    OUTPUT_DIR / "most_concentrated_lifecycles.csv",
    index=False
)


print("\nMOST CONCENTRATED COMPLETE LIFECYCLES")
print(concentrated.to_string(index=False))


# --------------------------------------------------
# 6. Most sustained high-volume products
# --------------------------------------------------

sustained = con.execute(
    f"""
    SELECT
        article_id,
        prod_name,
        product_type_name,
        garment_group_name,

        observed_lifespan_days,
        total_units,

        days_to_50_pct,
        days_to_80_pct,

        max_7d_demand_share_pct,
        post_peak_share_pct

    FROM read_parquet('{lifecycle_performance}')

    WHERE complete_lifecycle = 1
      AND total_units >= 1000

    ORDER BY
        max_7d_demand_share_pct ASC,
        total_units DESC

    LIMIT 20
    """
).fetchdf()


sustained.to_csv(
    OUTPUT_DIR / "sustained_high_volume_articles.csv",
    index=False
)


print("\nSUSTAINED HIGH-VOLUME COMPLETE LIFECYCLES")
print(sustained.to_string(index=False))


con.close()

print("\nCumulative lifecycle analysis complete.")