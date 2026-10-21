"""Shared SQL for retrospective finite differences and deterministic extrema."""


def momentum_query(source):
    """Source is an internal SQL relation name, not user input."""
    return f"""
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

            FROM {source}
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
    """


def peak_date_sql(metric, minimum=False):
    if metric not in {"units_ma7", "demand_velocity", "demand_acceleration"}:
        raise ValueError("Unknown momentum metric")
    direction = "ASC" if minimum else "DESC"
    return f"FIRST(date ORDER BY {metric} {direction}, date ASC) FILTER (WHERE {metric} IS NOT NULL)"


def lifecycle_profile_sql(p25_7d, p75_7d, p25_days80, p75_days80, p75_units, p75_post_peak):
    return f"""
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

            END
    """
