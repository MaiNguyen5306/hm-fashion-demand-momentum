from pathlib import Path
import duckdb


# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PRODUCT_PROFILES = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "product_profiles.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

product_profiles = PRODUCT_PROFILES.as_posix()


# --------------------------------------------------
# DuckDB setup
# --------------------------------------------------

con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")


print("\nBUILDING H&M GARMENT-GROUP BUSINESS INSIGHTS")
print("=" * 65)


# --------------------------------------------------
# 1. Overall garment-group summary
# --------------------------------------------------

garment_summary = con.execute(
    f"""
    SELECT
        garment_group_name,

        COUNT(*) AS eligible_articles,

        SUM(total_units) AS total_units,

        ROUND(
            AVG(total_units),
            1
        ) AS avg_units_per_article,

        SUM(
            CASE
                WHEN complete_lifecycle = 1
                THEN 1
                ELSE 0
            END
        ) AS complete_lifecycle_articles,

        SUM(
            CASE
                WHEN complete_lifecycle = 0
                THEN 1
                ELSE 0
            END
        ) AS partial_lifecycle_articles,


        -- -----------------------------------
        -- Lifecycle profile counts
        -- Complete lifecycles only
        -- -----------------------------------

        SUM(
            CASE
                WHEN lifecycle_profile = 'Sustained Performer'
                THEN 1
                ELSE 0
            END
        ) AS sustained_performers,

        SUM(
            CASE
                WHEN lifecycle_profile = 'Rapid Spike'
                THEN 1
                ELSE 0
            END
        ) AS rapid_spikes,

        SUM(
            CASE
                WHEN lifecycle_profile = 'Long Tail'
                THEN 1
                ELSE 0
            END
        ) AS long_tail_articles,

        SUM(
            CASE
                WHEN lifecycle_profile = 'Slow Burn'
                THEN 1
                ELSE 0
            END
        ) AS slow_burn_articles,


        -- -----------------------------------
        -- Lifecycle shares
        -- Denominator = complete lifecycles
        -- -----------------------------------

        ROUND(
            100.0
            * SUM(
                CASE
                    WHEN lifecycle_profile = 'Sustained Performer'
                    THEN 1
                    ELSE 0
                END
            )
            / NULLIF(
                SUM(
                    CASE
                        WHEN complete_lifecycle = 1
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ),
            2
        ) AS sustained_share_complete_pct,


        ROUND(
            100.0
            * SUM(
                CASE
                    WHEN lifecycle_profile = 'Rapid Spike'
                    THEN 1
                    ELSE 0
                END
            )
            / NULLIF(
                SUM(
                    CASE
                        WHEN complete_lifecycle = 1
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ),
            2
        ) AS rapid_spike_share_complete_pct,


        ROUND(
            100.0
            * SUM(
                CASE
                    WHEN lifecycle_profile = 'Long Tail'
                    THEN 1
                    ELSE 0
                END
            )
            / NULLIF(
                SUM(
                    CASE
                        WHEN complete_lifecycle = 1
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ),
            2
        ) AS long_tail_share_complete_pct,


        -- -----------------------------------
        -- Momentum
        -- -----------------------------------

        SUM(
            CASE
                WHEN momentum_tier = 'Extreme Momentum'
                THEN 1
                ELSE 0
            END
        ) AS extreme_momentum_articles,

        ROUND(
            100.0
            * SUM(
                CASE
                    WHEN momentum_tier = 'Extreme Momentum'
                    THEN 1
                    ELSE 0
                END
            )
            / COUNT(*),
            2
        ) AS extreme_momentum_share_pct,


        ROUND(
            AVG(peak_relative_velocity),
            2
        ) AS avg_peak_relative_velocity,


        ROUND(
            MEDIAN(max_7d_demand_share_pct),
            2
        ) AS median_max_7d_share_pct,


        ROUND(
            MEDIAN(days_to_80_pct),
            1
        ) AS median_days_to_80


    FROM read_parquet('{product_profiles}')

    GROUP BY garment_group_name

    ORDER BY total_units DESC
    """
).fetchdf()


garment_summary.to_csv(
    OUTPUT_DIR / "garment_group_business_summary.csv",
    index=False
)


print("\nGARMENT GROUP BUSINESS SUMMARY")
print(garment_summary.to_string(index=False))


# --------------------------------------------------
# 2. Lifecycle profile mix
# --------------------------------------------------

lifecycle_mix = con.execute(
    f"""
    SELECT
        garment_group_name,
        lifecycle_profile,

        COUNT(*) AS articles,

        ROUND(
            100.0
            * COUNT(*)
            / SUM(COUNT(*)) OVER (
                PARTITION BY garment_group_name
            ),
            2
        ) AS profile_share_pct

    FROM read_parquet('{product_profiles}')

    WHERE complete_lifecycle = 1

    GROUP BY
        garment_group_name,
        lifecycle_profile

    ORDER BY
        garment_group_name,
        articles DESC
    """
).fetchdf()


lifecycle_mix.to_csv(
    OUTPUT_DIR / "garment_group_lifecycle_mix.csv",
    index=False
)


# --------------------------------------------------
# 3. Momentum tier mix
# --------------------------------------------------

momentum_mix = con.execute(
    f"""
    SELECT
        garment_group_name,
        momentum_tier,

        COUNT(*) AS articles,

        ROUND(
            100.0
            * COUNT(*)
            / SUM(COUNT(*)) OVER (
                PARTITION BY garment_group_name
            ),
            2
        ) AS tier_share_pct

    FROM read_parquet('{product_profiles}')

    GROUP BY
        garment_group_name,
        momentum_tier

    ORDER BY
        garment_group_name,
        articles DESC
    """
).fetchdf()


momentum_mix.to_csv(
    OUTPUT_DIR / "garment_group_momentum_mix.csv",
    index=False
)


# --------------------------------------------------
# 4. Standout garment groups
# --------------------------------------------------
# Use at least 100 complete lifecycles so tiny groups
# do not dominate percentage-based rankings.
# --------------------------------------------------

standouts = con.execute(
    f"""
    WITH group_summary AS (

        SELECT
            garment_group_name,

            COUNT(*) AS eligible_articles,

            SUM(
                CASE
                    WHEN complete_lifecycle = 1
                    THEN 1
                    ELSE 0
                END
            ) AS complete_articles,


            100.0
            * SUM(
                CASE
                    WHEN lifecycle_profile = 'Sustained Performer'
                    THEN 1
                    ELSE 0
                END
            )
            /
            NULLIF(
                SUM(
                    CASE
                        WHEN complete_lifecycle = 1
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS sustained_share,


            100.0
            * SUM(
                CASE
                    WHEN lifecycle_profile = 'Rapid Spike'
                    THEN 1
                    ELSE 0
                END
            )
            /
            NULLIF(
                SUM(
                    CASE
                        WHEN complete_lifecycle = 1
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS rapid_spike_share,


            100.0
            * SUM(
                CASE
                    WHEN lifecycle_profile = 'Long Tail'
                    THEN 1
                    ELSE 0
                END
            )
            /
            NULLIF(
                SUM(
                    CASE
                        WHEN complete_lifecycle = 1
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS long_tail_share,


            100.0
            * SUM(
                CASE
                    WHEN momentum_tier = 'Extreme Momentum'
                    THEN 1
                    ELSE 0
                END
            )
            / COUNT(*) AS extreme_momentum_share


        FROM read_parquet('{product_profiles}')

        GROUP BY garment_group_name
    )


    SELECT
        garment_group_name,
        eligible_articles,
        complete_articles,

        ROUND(sustained_share, 2)
            AS sustained_share_pct,

        ROUND(rapid_spike_share, 2)
            AS rapid_spike_share_pct,

        ROUND(long_tail_share, 2)
            AS long_tail_share_pct,

        ROUND(extreme_momentum_share, 2)
            AS extreme_momentum_share_pct


    FROM group_summary

    WHERE complete_articles >= 100

    ORDER BY garment_group_name
    """
).fetchdf()


standouts.to_csv(
    OUTPUT_DIR / "garment_group_standouts.csv",
    index=False
)


print("\nGARMENT GROUPS WITH >=100 COMPLETE LIFECYCLES")
print(standouts.to_string(index=False))


# --------------------------------------------------
# 5. Top groups by each business behavior
# --------------------------------------------------

print("\nTOP 5: SUSTAINED PERFORMER SHARE")

top_sustained = (
    standouts
    .sort_values(
        "sustained_share_pct",
        ascending=False
    )
    .head(5)
)

print(top_sustained.to_string(index=False))


print("\nTOP 5: RAPID SPIKE SHARE")

top_spike = (
    standouts
    .sort_values(
        "rapid_spike_share_pct",
        ascending=False
    )
    .head(5)
)

print(top_spike.to_string(index=False))


print("\nTOP 5: LONG-TAIL SHARE")

top_long_tail = (
    standouts
    .sort_values(
        "long_tail_share_pct",
        ascending=False
    )
    .head(5)
)

print(top_long_tail.to_string(index=False))


print("\nTOP 5: EXTREME MOMENTUM SHARE")

top_extreme = (
    standouts
    .sort_values(
        "extreme_momentum_share_pct",
        ascending=False
    )
    .head(5)
)

print(top_extreme.to_string(index=False))


# --------------------------------------------------
# 6. Save rankings together
# --------------------------------------------------

top_sustained = top_sustained.copy()
top_sustained["behavior"] = "Sustained Performer"

top_spike = top_spike.copy()
top_spike["behavior"] = "Rapid Spike"

top_long_tail = top_long_tail.copy()
top_long_tail["behavior"] = "Long Tail"

top_extreme = top_extreme.copy()
top_extreme["behavior"] = "Extreme Momentum"


rankings = (
    __import__("pandas")
    .concat(
        [
            top_sustained,
            top_spike,
            top_long_tail,
            top_extreme
        ],
        ignore_index=True
    )
)


rankings.to_csv(
    OUTPUT_DIR / "garment_group_behavior_rankings.csv",
    index=False
)


# --------------------------------------------------
# 7. Validation
# --------------------------------------------------

validation = con.execute(
    f"""
    SELECT
        COUNT(*) AS articles,
        SUM(total_units) AS total_units,
        COUNT(DISTINCT garment_group_name)
            AS garment_groups

    FROM read_parquet('{product_profiles}')
    """
).fetchdf()


validation.to_csv(
    OUTPUT_DIR / "category_insights_validation.csv",
    index=False
)


print("\nCATEGORY INSIGHTS VALIDATION")
print(validation.to_string(index=False))


con.close()

print("\nCategory insight analysis complete.")