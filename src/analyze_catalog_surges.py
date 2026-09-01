from pathlib import Path
import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONTEXTUAL_METRICS = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "contextual_momentum_metrics.parquet"
)

ARTICLE_DIM = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "article_dimension.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

contextual_metrics = CONTEXTUAL_METRICS.as_posix()
article_dim = ARTICLE_DIM.as_posix()

con = duckdb.connect()

con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")


print("\nANALYZING H&M CATALOG-WIDE DEMAND SURGES")
print("=" * 60)


# --------------------------------------------------
# 1. Daily catalog-level demand
# --------------------------------------------------

catalog_daily = con.execute(
    f"""
    SELECT
        date,

        SUM(daily_units) AS catalog_units,

        COUNT(DISTINCT article_id)
            AS active_articles,

        AVG(
            CASE
                WHEN valid_momentum_day = 1
                THEN demand_velocity
            END
        ) AS avg_article_velocity,

        AVG(
            CASE
                WHEN valid_momentum_day = 1
                THEN velocity_pct_of_typical_day
            END
        ) AS avg_relative_velocity,

        100.0 * SUM(
            CASE
                WHEN valid_momentum_day = 1
                 AND demand_velocity > 0
                THEN 1
                ELSE 0
            END
        )
        /
        NULLIF(
            SUM(
                CASE
                    WHEN valid_momentum_day = 1
                    THEN 1
                    ELSE 0
                END
            ),
            0
        ) AS positive_velocity_share_pct

    FROM read_parquet('{contextual_metrics}')

    GROUP BY date

    ORDER BY date
    """
).fetchdf()


catalog_daily.to_csv(
    OUTPUT_DIR / "catalog_surge_daily_summary.csv",
    index=False
)


# --------------------------------------------------
# 2. Highest-volume catalog days
# --------------------------------------------------

top_volume_days = catalog_daily.sort_values(
    "catalog_units",
    ascending=False
).head(20)


top_volume_days.to_csv(
    OUTPUT_DIR / "top_catalog_volume_days.csv",
    index=False
)


print("\nTOP 20 CATALOG DAYS BY UNIT VOLUME")
print(top_volume_days.to_string(index=False))


# --------------------------------------------------
# 3. Broadest positive-momentum days
# --------------------------------------------------

top_momentum_days = (
    catalog_daily
    .dropna(subset=["positive_velocity_share_pct"])
    .sort_values(
        "positive_velocity_share_pct",
        ascending=False
    )
    .head(20)
)


top_momentum_days.to_csv(
    OUTPUT_DIR / "top_catalog_momentum_days.csv",
    index=False
)


print("\nTOP 20 DAYS BY SHARE OF PRODUCTS WITH POSITIVE VELOCITY")
print(top_momentum_days.to_string(index=False))


# --------------------------------------------------
# 4. Late-November 2019 event window
# --------------------------------------------------

event_window = con.execute(
    f"""
    SELECT
        date,

        SUM(daily_units) AS catalog_units,

        COUNT(DISTINCT article_id)
            AS active_articles,

        AVG(
            CASE
                WHEN valid_momentum_day = 1
                THEN demand_velocity
            END
        ) AS avg_article_velocity,

        AVG(
            CASE
                WHEN valid_momentum_day = 1
                THEN velocity_pct_of_typical_day
            END
        ) AS avg_relative_velocity,

        100.0 * SUM(
            CASE
                WHEN valid_momentum_day = 1
                 AND demand_velocity > 0
                THEN 1
                ELSE 0
            END
        )
        /
        NULLIF(
            SUM(
                CASE
                    WHEN valid_momentum_day = 1
                    THEN 1
                    ELSE 0
                END
            ),
            0
        ) AS positive_velocity_share_pct

    FROM read_parquet('{contextual_metrics}')

    WHERE date BETWEEN DATE '2019-11-20'
                   AND DATE '2019-12-03'

    GROUP BY date

    ORDER BY date
    """
).fetchdf()


event_window.to_csv(
    OUTPUT_DIR / "nov2019_surge_window.csv",
    index=False
)


print("\nLATE-NOVEMBER 2019 WINDOW")
print(event_window.to_string(index=False))


# --------------------------------------------------
# 5. Compare event window with prior 28 days
# --------------------------------------------------

period_comparison = con.execute(
    f"""
    WITH daily AS (

        SELECT
            date,
            SUM(daily_units) AS catalog_units,

            AVG(
                CASE
                    WHEN valid_momentum_day = 1
                    THEN demand_velocity
                END
            ) AS avg_article_velocity,

            100.0 * SUM(
                CASE
                    WHEN valid_momentum_day = 1
                     AND demand_velocity > 0
                    THEN 1
                    ELSE 0
                END
            )
            /
            NULLIF(
                SUM(
                    CASE
                        WHEN valid_momentum_day = 1
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS positive_velocity_share_pct

        FROM read_parquet('{contextual_metrics}')

        GROUP BY date
    )

    SELECT
        CASE
            WHEN date BETWEEN DATE '2019-11-20'
                          AND DATE '2019-12-03'
                THEN 'Late Nov / Early Dec 2019'

            WHEN date BETWEEN DATE '2019-10-23'
                          AND DATE '2019-11-19'
                THEN 'Prior 28 Days'
        END AS period,

        COUNT(*) AS days,

        ROUND(AVG(catalog_units), 2)
            AS avg_daily_units,

        ROUND(MAX(catalog_units), 2)
            AS peak_daily_units,

        ROUND(AVG(avg_article_velocity), 4)
            AS avg_article_velocity,

        ROUND(AVG(positive_velocity_share_pct), 2)
            AS avg_positive_velocity_share_pct

    FROM daily

    WHERE date BETWEEN DATE '2019-10-23'
                   AND DATE '2019-12-03'

    GROUP BY period

    ORDER BY period
    """
).fetchdf()


period_comparison.to_csv(
    OUTPUT_DIR / "nov2019_period_comparison.csv",
    index=False
)


print("\nEVENT WINDOW VS PRIOR 28 DAYS")
print(period_comparison.to_string(index=False))


# --------------------------------------------------
# 6. Garment groups driving the event window
# --------------------------------------------------

garment_contribution = con.execute(
    f"""
    SELECT
        d.garment_group_name,

        SUM(c.daily_units) AS units_sold,

        ROUND(
            100.0
            * SUM(c.daily_units)
            / SUM(SUM(c.daily_units)) OVER (),
            2
        ) AS event_unit_share_pct,

        AVG(
            CASE
                WHEN c.valid_momentum_day = 1
                THEN c.demand_velocity
            END
        ) AS avg_velocity,

        AVG(
            CASE
                WHEN c.valid_momentum_day = 1
                THEN c.velocity_pct_of_typical_day
            END
        ) AS avg_relative_velocity

    FROM read_parquet('{contextual_metrics}') AS c

    INNER JOIN read_parquet('{article_dim}') AS d
        ON c.article_id = d.article_id

    WHERE c.date BETWEEN DATE '2019-11-20'
                     AND DATE '2019-12-03'

    GROUP BY d.garment_group_name

    ORDER BY units_sold DESC
    """
).fetchdf()


garment_contribution.to_csv(
    OUTPUT_DIR / "nov2019_garment_contribution.csv",
    index=False
)


print("\nTOP GARMENT GROUPS DURING EVENT WINDOW")
print(garment_contribution.head(15).to_string(index=False))


con.close()

print("\nCatalog surge analysis complete.")