"""Hand-computed boundaries and ties for production SQL expressions."""

import unittest

import duckdb
import pandas as pd

from src.demand_math import momentum_query, peak_date_sql, lifecycle_profile_sql


class DemandMathTests(unittest.TestCase):
    def test_full_windows_and_central_differences(self):
        # A quadratic demand curve has a known interior velocity and acceleration.
        frame = pd.DataFrame({"article_id": ["0000000001"] * 15,
                              "date": pd.date_range("2020-01-01", periods=15),
                              "daily_units": [t*t for t in range(15)]})
        with duckdb.connect() as con:
            con.register("raw", frame)
            con.execute("""CREATE VIEW panel AS SELECT *,
                AVG(daily_units) OVER w AS units_ma7, COUNT(*) OVER w AS ma7_window_days,
                MIN(date) OVER () AS first_sale_date, MAX(date) OVER () AS last_sale_date,
                15 AS observed_lifespan_days, 0 AS left_censored, 0 AS right_censored,
                1 AS complete_lifecycle FROM raw
                WINDOW w AS (ORDER BY date ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING)
            """)
            result = con.sql(momentum_query("panel")).df().sort_values("date")
        self.assertEqual(result.valid_momentum_day.tolist(), [0]*4 + [1]*7 + [0]*4)
        self.assertEqual(result.iloc[7].demand_velocity, 14)
        self.assertAlmostEqual(result.iloc[7].demand_acceleration, 2)
        self.assertTrue(result.loc[result.valid_momentum_day.eq(0), "demand_velocity"].isna().all())
        self.assertEqual(result.iloc[0].ma7_window_days, 4)

    def test_tied_extrema_choose_earliest_independent_of_order(self):
        for reverse in [False, True]:
            with duckdb.connect() as con:
                con.execute("""CREATE TABLE observations AS SELECT * FROM (VALUES
                    (DATE '2020-01-03', 5.0, -2.0), (DATE '2020-01-02', 5.0, -2.0),
                    (DATE '2020-01-01', NULL, NULL)) t(date, units_ma7, demand_velocity)""")
                direction = 'DESC' if reverse else 'ASC'
                peak, trough = con.sql(f"SELECT {peak_date_sql('units_ma7')}, {peak_date_sql('demand_velocity', minimum=True)} FROM (SELECT * FROM observations ORDER BY date {direction})").fetchone()
            self.assertEqual(str(peak)[:10], "2020-01-02")
            self.assertEqual(str(trough)[:10], "2020-01-02")

    def test_all_null_extrema_remain_null(self):
        with duckdb.connect() as con:
            result = con.sql(f"SELECT {peak_date_sql('units_ma7')} FROM (SELECT DATE '2020-01-01' AS date, NULL::DOUBLE AS units_ma7)").fetchone()[0]
        self.assertIsNone(result)

    def test_profile_threshold_boundaries_and_precedence(self):
        expression = lifecycle_profile_sql(10, 25, 70, 180, 687, 79)
        with duckdb.connect() as con:
            result = con.sql(f"""SELECT {expression} FROM (VALUES
                (0, 25, 70, 1000, 90),
                (1, 25, 70, 1000, 90),
                (1, 10, 180, 687, 90),
                (1, 10, 180, 686, 90),
                (1, 24, 100, 200, 79),
                (1, 25, 100, 200, 79)
            ) p(complete_lifecycle,max_7d_demand_share_pct,days_to_80_pct,total_units,post_peak_share_pct)""").fetchall()
        self.assertEqual([row[0] for row in result], [
            'Partial Lifecycle', 'Rapid Spike', 'Sustained Performer',
            'Slow Burn', 'Long Tail', 'Balanced Lifecycle'])


if __name__ == "__main__":
    unittest.main()
