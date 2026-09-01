from pathlib import Path
import duckdb


# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

LIFECYCLE_PERFORMANCE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "lifecycle_performance_summary.parquet"
)

ARTICLE_LIFECYCLE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "article_lifecycle.parquet"
)

CONTEXTUAL_MOMENTUM = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "contextual_momentum_metrics.parquet"
)

PRODUCT_PROFILES = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "product_profiles.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


lifecycle_performance = LIFECYCLE_PERFORMANCE.as_posix()
article_lifecycle = ARTICLE_LIFECYCLE.as_posix()
contextual_momentum = CONTEXTUAL_MOMENTUM.as_posix()
product_profiles = PRODUCT_PROFILES.as_posix()


# --------------------------------------------------
# DuckDB setup
# --------------------------------------------------

con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")
con.execute("SET preserve_insertion_order = false")


print("\nBUILDING H&M PRODUCT LIFECYCLE PROFILES")
print("=" * 60)


# --------------------------------------------------
# 1. Determine lifecycle thresholds
# --------------------------------------------------

lifecycle_thresholds = con.execute(
    f"""
    SELECT

        PERCENTILE_CONT(0.25)
            WITHIN GROUP (
                ORDER BY max_7d_demand_share_pct
            ) AS p25_7d_share,

        MEDIAN(max_7d_demand_share_pct)
            AS median_7d_share,

        PERCENTILE_CONT(0.75)
            WITHIN GROUP (
                ORDER BY max_7d_demand_share_pct
            ) AS p75_7d_share,


        PERCENTILE_CONT(0.25)
            WITHIN GROUP (
                ORDER BY days_to_80_pct
            ) AS p25_days_to_80,

        MEDIAN(days_to_80_pct)
            AS median_days_to_80,

        PERCENTILE_CONT(0.75)
            WITHIN GROUP (
                ORDER BY days_to_80_pct
            ) AS p75_days_to_80,


        PERCENTILE_CONT(0.75)
            WITHIN GROUP (
                ORDER BY total_units
            ) AS p75_total_units,


        PERCENTILE_CONT(0.75)
            WITHIN GROUP (
                ORDER BY post_peak_share_pct
            ) AS p75_post_peak_share


    FROM read_parquet('{lifecycle_performance}')

    WHERE complete_lifecycle = 1
    """
).fetchdf()


print("\nLIFECYCLE PROFILE THRESHOLDS")
print(lifecycle_thresholds.to_string(index=False))


lifecycle_thresholds.to_csv(
    OUTPUT_DIR / "product_profile_thresholds.csv",
    index=False
)


# Pull values for use in SQL
p25_7d = float(
    lifecycle_thresholds.loc[0, "p25_7d_share"]
)

p75_7d = float(
    lifecycle_thresholds.loc[0, "p75_7d_share"]
)

p25_days80 = float(
    lifecycle_thresholds.loc[0, "p25_days_to_80"]
)

p75_days80 = float(
    lifecycle_thresholds.loc[0, "p75_days_to_80"]
)

p75_units = float(
    lifecycle_thresholds.loc[0, "p75_total_units"]
)

p75_post_peak = float(
    lifecycle_thresholds.loc[0, "p75_post_peak_share"]
)


# --------------------------------------------------
# 2. Article-level momentum summary
# --------------------------------------------------

print("\nCreating article-level momentum features...")


con.execute(
    f"""
    CREATE OR REPLACE TEMP TABLE article_relative_momentum AS

    SELECT
        article_id,

        MAX(
            CASE
                WHEN valid_momentum_day = 1
                THEN velocity_pct_of_typical_day
            END
        ) AS peak_relative_velocity,

        MAX(
            CASE
                WHEN valid_momentum_day = 1
                THEN demand_velocity
            END
        ) AS peak_absolute_velocity

    FROM read_parquet('{contextual_momentum}')

    GROUP BY article_id
    """
)


# --------------------------------------------------
# 3. Determine momentum thresholds
# --------------------------------------------------

momentum_thresholds = con.execute(
    """
    SELECT

        PERCENTILE_CONT(0.25)
            WITHIN GROUP (
                ORDER BY peak_relative_velocity
            ) AS p25_peak_relative_velocity,

        PERCENTILE_CONT(0.75)
            WITHIN GROUP (
                ORDER BY peak_relative_velocity
            ) AS p75_peak_relative_velocity,

        PERCENTILE_CONT(0.90)
            WITHIN GROUP (
                ORDER BY peak_relative_velocity
            ) AS p90_peak_relative_velocity

    FROM article_relative_momentum
    """
).fetchdf()


print("\nMOMENTUM PROFILE THRESHOLDS")
print(momentum_thresholds.to_string(index=False))


p25_momentum = float(
    momentum_thresholds.loc[
        0,
        "p25_peak_relative_velocity"
    ]
)

p75_momentum = float(
    momentum_thresholds.loc[
        0,
        "p75_peak_relative_velocity"
    ]
)

p90_momentum = float(
    momentum_thresholds.loc[
        0,
        "p90_peak_relative_velocity"
    ]
)


# Add momentum thresholds to the saved threshold file
combined_thresholds = lifecycle_thresholds.copy()

combined_thresholds[
    "p25_peak_relative_velocity"
] = p25_momentum

combined_thresholds[
    "p75_peak_relative_velocity"
] = p75_momentum

combined_thresholds[
    "p90_peak_relative_velocity"
] = p90_momentum


combined_thresholds.to_csv(
    OUTPUT_DIR / "product_profile_thresholds.csv",
    index=False
)


# --------------------------------------------------
# 4. Build product profiles
# --------------------------------------------------

print("\nAssigning lifecycle and momentum profiles...")


con.execute(
    f"""
    COPY (

        SELECT
            p.article_id,

            p.prod_name,
            p.product_type_name,
            p.garment_group_name,

            p.first_sale_date,
            p.last_sale_date,

            p.observed_lifespan_days,
            l.active_sales_days,
            l.active_day_rate_pct,

            p.total_units,

            p.days_to_50_pct,
            p.days_to_80_pct,

            p.max_7d_demand_share_pct,
            p.post_peak_share_pct,

            p.complete_lifecycle,

            m.peak_absolute_velocity,
            m.peak_relative_velocity,


            -- -----------------------------------
            -- Lifecycle shape
            -- -----------------------------------

            CASE

                WHEN p.complete_lifecycle = 0
                    THEN 'Partial Lifecycle'


                WHEN p.max_7d_demand_share_pct >= {p75_7d}
                 AND p.days_to_80_pct <= {p25_days80}
                    THEN 'Rapid Spike'


                WHEN p.max_7d_demand_share_pct <= {p25_7d}
                 AND p.days_to_80_pct >= {p75_days80}
                 AND p.total_units >= {p75_units}
                    THEN 'Sustained Performer'


                WHEN p.max_7d_demand_share_pct <= {p25_7d}
                 AND p.days_to_80_pct >= {p75_days80}
                    THEN 'Slow Burn'


                WHEN p.post_peak_share_pct >= {p75_post_peak}
                 AND p.max_7d_demand_share_pct < {p75_7d}
                    THEN 'Long Tail'


                ELSE 'Balanced Lifecycle'

            END AS lifecycle_profile,


            -- -----------------------------------
            -- Momentum intensity
            -- -----------------------------------

            CASE

                WHEN m.peak_relative_velocity
                     >= {p90_momentum}
                    THEN 'Extreme Momentum'


                WHEN m.peak_relative_velocity
                     >= {p75_momentum}
                    THEN 'High Momentum'


                WHEN m.peak_relative_velocity
                     >= {p25_momentum}
                    THEN 'Typical Momentum'


                ELSE 'Low Momentum'

            END AS momentum_tier


        FROM read_parquet(
            '{lifecycle_performance}'
        ) AS p


        INNER JOIN read_parquet(
            '{article_lifecycle}'
        ) AS l
            ON p.article_id = l.article_id


        INNER JOIN article_relative_momentum AS m
            ON p.article_id = m.article_id
    )

    TO '{product_profiles}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)


print("Product profile table created.")


# --------------------------------------------------
# 5. Lifecycle profile counts
# --------------------------------------------------

lifecycle_counts = con.execute(
    f"""
    SELECT
        lifecycle_profile,

        COUNT(*) AS articles,

        ROUND(
            100.0
            * COUNT(*)
            / SUM(COUNT(*)) OVER (),
            2
        ) AS pct_articles,

        SUM(total_units)
            AS total_units,

        ROUND(
            AVG(total_units),
            1
        ) AS avg_units_per_article


    FROM read_parquet('{product_profiles}')

    GROUP BY lifecycle_profile

    ORDER BY articles DESC
    """
).fetchdf()


lifecycle_counts.to_csv(
    OUTPUT_DIR / "lifecycle_profile_counts.csv",
    index=False
)


print("\nLIFECYCLE PROFILE COUNTS")
print(lifecycle_counts.to_string(index=False))


# --------------------------------------------------
# 6. Momentum tier counts
# --------------------------------------------------

momentum_counts = con.execute(
    f"""
    SELECT
        momentum_tier,

        COUNT(*) AS articles,

        ROUND(
            100.0
            * COUNT(*)
            / SUM(COUNT(*)) OVER (),
            2
        ) AS pct_articles,

        ROUND(
            AVG(peak_relative_velocity),
            2
        ) AS avg_peak_relative_velocity


    FROM read_parquet('{product_profiles}')

    GROUP BY momentum_tier

    ORDER BY
        CASE momentum_tier
            WHEN 'Extreme Momentum' THEN 1
            WHEN 'High Momentum' THEN 2
            WHEN 'Typical Momentum' THEN 3
            WHEN 'Low Momentum' THEN 4
        END
    """
).fetchdf()


momentum_counts.to_csv(
    OUTPUT_DIR / "momentum_tier_counts.csv",
    index=False
)


print("\nMOMENTUM TIER COUNTS")
print(momentum_counts.to_string(index=False))


# --------------------------------------------------
# 7. Cross-profile matrix
# --------------------------------------------------

profile_matrix = con.execute(
    f"""
    SELECT
        lifecycle_profile,
        momentum_tier,
        COUNT(*) AS articles

    FROM read_parquet('{product_profiles}')

    GROUP BY
        lifecycle_profile,
        momentum_tier

    ORDER BY
        lifecycle_profile,
        momentum_tier
    """
).fetchdf()


profile_matrix.to_csv(
    OUTPUT_DIR / "product_profile_matrix.csv",
    index=False
)


print("\nLIFECYCLE × MOMENTUM MATRIX")
print(profile_matrix.to_string(index=False))


# --------------------------------------------------
# 8. Example products from each lifecycle profile
# --------------------------------------------------

examples = con.execute(
    f"""
    WITH ranked AS (

        SELECT
            *,

            ROW_NUMBER() OVER (
                PARTITION BY lifecycle_profile
                ORDER BY total_units DESC
            ) AS profile_rank

        FROM read_parquet('{product_profiles}')
    )

    SELECT
        lifecycle_profile,
        momentum_tier,

        article_id,
        prod_name,
        product_type_name,
        garment_group_name,

        total_units,
        observed_lifespan_days,

        days_to_80_pct,

        ROUND(
            max_7d_demand_share_pct,
            2
        ) AS max_7d_demand_share_pct,

        ROUND(
            post_peak_share_pct,
            2
        ) AS post_peak_share_pct,

        ROUND(
            peak_relative_velocity,
            2
        ) AS peak_relative_velocity


    FROM ranked

    WHERE profile_rank <= 5

    ORDER BY
        lifecycle_profile,
        profile_rank
    """
).fetchdf()


examples.to_csv(
    OUTPUT_DIR / "product_profile_examples.csv",
    index=False
)


print("\nTOP EXAMPLES BY LIFECYCLE PROFILE")
print(examples.to_string(index=False))


# --------------------------------------------------
# 9. Validation
# --------------------------------------------------

validation = con.execute(
    f"""
    SELECT
        COUNT(*) AS articles,

        SUM(total_units)
            AS total_units,

        SUM(
            CASE
                WHEN lifecycle_profile IS NULL
                THEN 1
                ELSE 0
            END
        ) AS missing_lifecycle_profiles,

        SUM(
            CASE
                WHEN momentum_tier IS NULL
                THEN 1
                ELSE 0
            END
        ) AS missing_momentum_tiers,

        COUNT(
            DISTINCT lifecycle_profile
        ) AS lifecycle_profile_count,

        COUNT(
            DISTINCT momentum_tier
        ) AS momentum_tier_count

    FROM read_parquet('{product_profiles}')
    """
).fetchdf()


validation.to_csv(
    OUTPUT_DIR / "product_profile_validation.csv",
    index=False
)


print("\nPRODUCT PROFILE VALIDATION")
print(validation.to_string(index=False))


con.close()

print("\nProduct profiling complete.")