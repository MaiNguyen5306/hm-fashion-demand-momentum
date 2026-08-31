from pathlib import Path
import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]

LIFECYCLE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "article_lifecycle.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

lifecycle_path = LIFECYCLE_PATH.as_posix()

con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")


print("\nH&M MOMENTUM ELIGIBILITY PROFILE")
print("=" * 55)


# --------------------------------------------------
# 1. Lifecycle distributions
# --------------------------------------------------

distribution = con.execute(
    f"""
    SELECT
        COUNT(*) AS articles,

        MIN(total_units) AS min_total_units,
        PERCENTILE_CONT(0.25)
            WITHIN GROUP (ORDER BY total_units)
            AS p25_total_units,
        MEDIAN(total_units) AS median_total_units,
        PERCENTILE_CONT(0.75)
            WITHIN GROUP (ORDER BY total_units)
            AS p75_total_units,
        PERCENTILE_CONT(0.90)
            WITHIN GROUP (ORDER BY total_units)
            AS p90_total_units,

        MIN(active_sales_days) AS min_active_days,
        PERCENTILE_CONT(0.25)
            WITHIN GROUP (ORDER BY active_sales_days)
            AS p25_active_days,
        MEDIAN(active_sales_days) AS median_active_days,
        PERCENTILE_CONT(0.75)
            WITHIN GROUP (ORDER BY active_sales_days)
            AS p75_active_days,
        PERCENTILE_CONT(0.90)
            WITHIN GROUP (ORDER BY active_sales_days)
            AS p90_active_days,

        MIN(observed_lifespan_days) AS min_lifespan,
        PERCENTILE_CONT(0.25)
            WITHIN GROUP (ORDER BY observed_lifespan_days)
            AS p25_lifespan,
        MEDIAN(observed_lifespan_days) AS median_lifespan,
        PERCENTILE_CONT(0.75)
            WITHIN GROUP (ORDER BY observed_lifespan_days)
            AS p75_lifespan,
        PERCENTILE_CONT(0.90)
            WITHIN GROUP (ORDER BY observed_lifespan_days)
            AS p90_lifespan

    FROM read_parquet('{lifecycle_path}')
    """
).fetchdf()

distribution.to_csv(
    OUTPUT_DIR / "lifecycle_distribution_summary.csv",
    index=False
)

print("\nLIFECYCLE DISTRIBUTIONS")
print(distribution.to_string(index=False))


# --------------------------------------------------
# 2. Candidate momentum populations
# --------------------------------------------------

scenarios = con.execute(
    f"""
    WITH scenarios AS (

        SELECT
            'A: >= 10 active days' AS scenario,
            COUNT(*) AS eligible_articles
        FROM read_parquet('{lifecycle_path}')
        WHERE active_sales_days >= 10

        UNION ALL

        SELECT
            'B: >= 20 active days + 50 units',
            COUNT(*)
        FROM read_parquet('{lifecycle_path}')
        WHERE active_sales_days >= 20
          AND total_units >= 50

        UNION ALL

        SELECT
            'C: >= 30 active days + 100 units',
            COUNT(*)
        FROM read_parquet('{lifecycle_path}')
        WHERE active_sales_days >= 30
          AND total_units >= 100

        UNION ALL

        SELECT
            'D: >= 60 active days + 250 units',
            COUNT(*)
        FROM read_parquet('{lifecycle_path}')
        WHERE active_sales_days >= 60
          AND total_units >= 250

        UNION ALL

        SELECT
            'E: C + complete observed lifecycle',
            COUNT(*)
        FROM read_parquet('{lifecycle_path}')
        WHERE active_sales_days >= 30
          AND total_units >= 100
          AND left_censored = 0
          AND right_censored = 0
    )

    SELECT
        scenario,
        eligible_articles,
        ROUND(
            100.0 * eligible_articles / 104547,
            2
        ) AS pct_of_articles

    FROM scenarios
    """
).fetchdf()

scenarios.to_csv(
    OUTPUT_DIR / "momentum_eligibility_scenarios.csv",
    index=False
)

print("\nCANDIDATE ELIGIBILITY RULES")
print(scenarios.to_string(index=False))


# --------------------------------------------------
# 3. Sparsity profile
# --------------------------------------------------

sparsity = con.execute(
    f"""
    SELECT
        CASE
            WHEN active_day_rate_pct < 10
                THEN '<10%'
            WHEN active_day_rate_pct < 25
                THEN '10-25%'
            WHEN active_day_rate_pct < 50
                THEN '25-50%'
            WHEN active_day_rate_pct < 75
                THEN '50-75%'
            ELSE '75-100%'
        END AS active_day_rate_bucket,

        COUNT(*) AS articles,

        ROUND(
            100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
            2
        ) AS pct_articles

    FROM read_parquet('{lifecycle_path}')

    GROUP BY active_day_rate_bucket

    ORDER BY
        MIN(active_day_rate_pct)
    """
).fetchdf()

sparsity.to_csv(
    OUTPUT_DIR / "lifecycle_sparsity_summary.csv",
    index=False
)

print("\nSALES-DAY DENSITY")
print(sparsity.to_string(index=False))


con.close()

print("\nMomentum eligibility profiling complete.")