"""Fail on invalid analytical grains, population drift, or formula inconsistencies."""

import json
from pathlib import Path

import duckdb

from demand_math import lifecycle_profile_sql


ROOT = Path(__file__).resolve().parents[1]


def main():
    checks = {}
    destination = ROOT / "outputs/analysis_validation.json"
    destination.write_text(json.dumps({"passed": False, "status": "running"}) + "\n")
    with duckdb.connect() as con:
        con.execute("SET threads = 2")
        con.execute("SET memory_limit = '3GB'")
        tables = {
            "lifecycle": "article_lifecycle", "panel": "momentum_daily_panel",
            "momentum": "momentum_metrics", "contextual": "contextual_momentum_metrics",
            "cumulative": "cumulative_lifecycle_daily", "performance": "lifecycle_performance_summary",
            "profiles": "product_profiles",
            "article_momentum": "article_momentum_summary",
            "fact": "daily_article_sales", "dimension": "article_dimension",
        }
        for alias, filename in tables.items():
            con.read_parquet(str(ROOT / "data/processed" / f"{filename}.parquet")).create_view(alias)

        def expect(name, sql, expected=0):
            actual = con.execute(sql).fetchone()[0]
            checks[name] = {"actual": actual, "expected": expected}
            if actual != expected:
                destination.write_text(json.dumps({"passed": False, "checks": checks}, indent=2) + "\n")
                raise ValueError(f"{name}: expected {expected}, got {actual}")

        expect("purchased_articles", "SELECT COUNT(*) FROM lifecycle", 104_547)
        expect("all_lifecycle_units", "SELECT CAST(SUM(total_units) AS BIGINT) FROM lifecycle", 31_788_324)
        expect("eligible_articles", "SELECT COUNT(*) FROM lifecycle WHERE active_sales_days >= 30 AND total_units >= 100", 44_014)
        for table in ["panel", "momentum", "contextual", "cumulative"]:
            expect(f"{table}_rows", f"SELECT COUNT(*) FROM {table}", 15_380_104)
            expect(f"{table}_articles", f"SELECT COUNT(DISTINCT article_id) FROM {table}", 44_014)
            expect(f"{table}_units", f"SELECT CAST(SUM(daily_units) AS BIGINT) FROM {table}", 29_996_706)
            expect(f"{table}_duplicate_keys", f"SELECT COUNT(*) FROM (SELECT article_id,date FROM {table} GROUP BY ALL HAVING COUNT(*) > 1)")
            expect(f"{table}_invalid_keys_units", f"SELECT COUNT(*) FROM {table} WHERE article_id IS NULL OR date IS NULL OR daily_units IS NULL OR daily_units < 0")
        expect("date_gaps", """
            SELECT COUNT(*) FROM (
                SELECT date - LAG(date) OVER (PARTITION BY article_id ORDER BY date) AS gap FROM panel
            ) WHERE gap != 1
        """)
        expect("valid_momentum_rows", "SELECT SUM(valid_momentum_day) FROM momentum", 15_027_992)
        expect("complete_articles", "SELECT COUNT(*) FROM profiles WHERE complete_lifecycle=1", 31_833)
        for table in ["performance", "profiles"]:
            expect(f"{table}_articles", f"SELECT COUNT(*) FROM {table}", 44_014)
            expect(f"{table}_unique_articles", f"SELECT COUNT(DISTINCT article_id) FROM {table}", 44_014)
            expect(f"{table}_units", f"SELECT CAST(SUM(total_units) AS BIGINT) FROM {table}", 29_996_706)
        expect("invalid_momentum_windows", """
            SELECT COUNT(*) FROM momentum
            WHERE valid_momentum_day NOT IN (0,1) OR valid_momentum_day IS NULL
               OR (valid_momentum_day=1 AND (demand_velocity IS NULL OR demand_acceleration IS NULL))
               OR (valid_momentum_day=0 AND (demand_velocity IS NOT NULL OR demand_acceleration IS NOT NULL))
        """)
        expect("momentum_formula_errors", """
            WITH neighbors AS (
                SELECT *, LAG(units_ma7) OVER w AS prev,
                       LEAD(units_ma7) OVER w AS next
                FROM momentum WINDOW w AS (PARTITION BY article_id ORDER BY date)
            ) SELECT COUNT(*) FROM neighbors WHERE valid_momentum_day=1 AND (
                ABS(demand_velocity-(next-prev)/2.0)>1e-9 OR
                ABS(demand_acceleration-(next-2*units_ma7+prev))>1e-9)
        """)
        expect("relative_scale_errors", """
            SELECT COUNT(*) FROM contextual c JOIN lifecycle l USING (article_id)
            WHERE c.valid_momentum_day=1 AND (
                c.velocity_pct_of_typical_day IS NULL OR
                ABS(c.velocity_pct_of_typical_day-100*c.demand_velocity/l.avg_units_per_active_day)>1e-8 OR
                c.daily_velocity_percentile IS NULL OR c.daily_velocity_percentile NOT BETWEEN 0 AND 100 OR
                c.daily_relative_velocity_percentile IS NULL OR c.daily_relative_velocity_percentile NOT BETWEEN 0 AND 100)
        """)
        expect("cumulative_formula_errors", """
            WITH expected AS (
                SELECT *, SUM(daily_units) OVER (
                    PARTITION BY article_id ORDER BY date ROWS UNBOUNDED PRECEDING
                ) AS expected_units FROM cumulative
            ) SELECT COUNT(*) FROM expected WHERE cumulative_units IS NULL OR cumulative_share_pct IS NULL
                OR cumulative_units != expected_units
                OR ABS(cumulative_share_pct-100.0*expected_units/lifecycle_total_units)>1e-8
        """)
        expect("invalid_lifecycle_metrics", """
            SELECT COUNT(*) FROM performance WHERE cumulative_50_date IS NULL OR cumulative_80_date IS NULL
              OR cumulative_50_date > cumulative_80_date OR cumulative_80_date > last_sale_date
              OR cumulative_50_date < first_sale_date OR days_to_50_pct < 0
              OR days_to_80_pct >= observed_lifespan_days
              OR pre_peak_units+peak_date_units+post_peak_units != total_units
              OR max_7d_demand_share_pct NOT BETWEEN 0 AND 100
        """)
        expect("missing_classifications", "SELECT COUNT(*) FROM profiles WHERE lifecycle_profile IS NULL OR momentum_tier IS NULL")
        expect("lifecycle_label_count", "SELECT COUNT(DISTINCT lifecycle_profile) FROM profiles", 6)
        expect("momentum_label_count", "SELECT COUNT(DISTINCT momentum_tier) FROM profiles", 4)
        expect("partial_classification_errors", "SELECT COUNT(*) FROM profiles WHERE (complete_lifecycle=0) != (lifecycle_profile='Partial Lifecycle')")
        expect("history_article_coverage_errors", """
            SELECT COUNT(*) FROM profiles p FULL JOIN (
                SELECT DISTINCT article_id FROM contextual
            ) c USING(article_id) WHERE p.article_id IS NULL OR c.article_id IS NULL
        """)
        expect("smoothing_errors", """
            WITH expected AS (
                SELECT *, AVG(daily_units) OVER w AS expected_ma7,
                       COUNT(*) OVER w AS expected_days FROM panel
                WINDOW w AS (PARTITION BY article_id ORDER BY date ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING)
            ) SELECT COUNT(*) FROM expected WHERE units_ma7 IS NULL OR ma7_window_days IS NULL
                OR ABS(units_ma7-expected_ma7)>1e-9 OR ma7_window_days != expected_days
        """)
        expect("momentum_edge_mask_errors", """
            WITH windows AS (
                SELECT *, LAG(ma7_window_days) OVER w AS prev_days,
                       LEAD(ma7_window_days) OVER w AS next_days FROM momentum
                WINDOW w AS (PARTITION BY article_id ORDER BY date)
            ) SELECT COUNT(*) FROM windows WHERE valid_momentum_day !=
                CASE WHEN ma7_window_days=7 AND prev_days=7 AND next_days=7 THEN 1 ELSE 0 END
        """)
        expect("peak_date_tie_errors", """
            WITH peaks AS (
                SELECT article_id, FIRST(date ORDER BY units_ma7 DESC,date ASC) AS expected_date
                FROM momentum GROUP BY article_id
            ) SELECT COUNT(*) FROM peaks JOIN article_momentum USING (article_id)
                WHERE peak_smoothed_demand_date IS DISTINCT FROM expected_date
        """)
        expect("milestone_date_errors", """
            WITH milestones AS (
                SELECT article_id,
                    MIN(date) FILTER (WHERE cumulative_units*2 >= lifecycle_total_units) AS date50,
                    MIN(date) FILTER (WHERE cumulative_units*5 >= lifecycle_total_units*4) AS date80
                FROM cumulative GROUP BY article_id
            ) SELECT COUNT(*) FROM milestones JOIN performance USING (article_id)
                WHERE cumulative_50_date IS DISTINCT FROM date50 OR cumulative_80_date IS DISTINCT FROM date80
        """)
        expect("peak_split_formula_errors", """
            WITH splits AS (
                SELECT c.article_id,
                    SUM(CASE WHEN c.date < m.peak_smoothed_demand_date THEN daily_units ELSE 0 END) AS pre,
                    SUM(CASE WHEN c.date = m.peak_smoothed_demand_date THEN daily_units ELSE 0 END) AS peak,
                    SUM(CASE WHEN c.date > m.peak_smoothed_demand_date THEN daily_units ELSE 0 END) AS post
                FROM cumulative c JOIN article_momentum m USING(article_id) GROUP BY c.article_id
            ) SELECT COUNT(*) FROM splits JOIN performance USING (article_id)
              WHERE pre_peak_units IS DISTINCT FROM pre OR peak_date_units IS DISTINCT FROM peak
                 OR post_peak_units IS DISTINCT FROM post
        """)
        expect("profile_peak_metadata_errors", """
            SELECT COUNT(*) FROM profiles p JOIN article_momentum m USING(article_id)
                JOIN lifecycle l USING(article_id) JOIN performance s USING(article_id)
            WHERE p.raw_peak_date IS DISTINCT FROM l.peak_date
               OR p.smoothed_peak_date IS DISTINCT FROM m.peak_smoothed_demand_date
               OR p.cumulative_50_date IS DISTINCT FROM s.cumulative_50_date
               OR p.cumulative_80_date IS DISTINCT FROM s.cumulative_80_date
        """)
        con.read_csv(str(ROOT / "outputs/product_profile_thresholds.csv")).create_view("thresholds")
        threshold = con.sql("SELECT * FROM thresholds").df().iloc[0]
        profile_expression = lifecycle_profile_sql(
            threshold.p25_7d_share, threshold.p75_7d_share,
            threshold.p25_days_to_80, threshold.p75_days_to_80,
            threshold.p75_total_units, threshold.p75_post_peak_share)
        expect("profile_threshold_errors", f"SELECT COUNT(*) FROM profiles p WHERE lifecycle_profile IS DISTINCT FROM ({profile_expression})")
        con.read_csv(str(ROOT / "outputs/garment_group_business_summary.csv")).create_view("category_summary")
        expect("category_population_errors", """
            WITH expected AS (
                SELECT garment_group_name,
                    ROUND(MEDIAN(max_7d_demand_share_pct),2) AS share,
                    ROUND(MEDIAN(days_to_80_pct),1) AS days80
                FROM profiles WHERE complete_lifecycle=1 GROUP BY garment_group_name
            ) SELECT COUNT(*) FROM expected JOIN category_summary USING(garment_group_name)
                WHERE median_max_7d_share_complete_pct IS DISTINCT FROM share
                   OR median_days_to_80_complete IS DISTINCT FROM days80
        """)
        con.read_csv(str(ROOT / "outputs/catalog_daily_momentum.csv")).create_view("catalog_summary")
        expect("catalog_population_errors", """
            WITH expected AS (
                SELECT date, COUNT(*) AS observed,
                    COUNT(*) FILTER (WHERE daily_units>0) AS selling FROM contextual GROUP BY date
            ) SELECT COUNT(*) FROM expected FULL JOIN catalog_summary USING(date)
                WHERE observed IS DISTINCT FROM observed_articles OR selling IS DISTINCT FROM selling_articles
        """)
        schemas = {}
        daily = {"panel", "momentum", "contextual", "cumulative"}
        for alias, filename in tables.items():
            columns = con.sql(f"DESCRIBE {alias}").df()
            schemas[filename] = {
                "path": f"data/processed/{filename}.parquet",
                "grain": "article_id × date" if alias in daily else (
                    "article_id × date × sales_channel_id" if alias == "fact" else "article_id"),
                "population": "full catalog" if alias == "dimension" else (
                    "all purchased articles" if alias in {"fact", "lifecycle"} else "momentum-eligible articles"),
                "columns": dict(zip(columns.column_name, columns.column_type)),
            }
        (ROOT / "outputs/data_schemas.json").write_text(json.dumps({"schema_version": 2, "tables": schemas}, indent=2) + "\n")
    destination.write_text(json.dumps({"passed": True, "checks": checks}, indent=2) + "\n")
    print(f"Passed {len(checks)} analytical checks. Report: {destination}")


if __name__ == "__main__":
    main()
