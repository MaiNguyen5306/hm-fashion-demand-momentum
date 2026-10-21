"""Local data access for every eligible product; independent of any web framework."""

from datetime import date
from pathlib import Path

import duckdb


DEFAULT_PROCESSED = Path(__file__).resolve().parents[1] / "data/processed"


class ProductDataStore:
    """Query local Parquet files without loading the full daily panel into Python."""

    def __init__(self, processed_dir=DEFAULT_PROCESSED):
        self.processed_dir = Path(processed_dir)

    def _connect(self):
        paths = {"profiles": self.processed_dir / "product_profiles.parquet",
                 "momentum": self.processed_dir / "contextual_momentum_metrics.parquet"}
        for path in paths.values():
            if not path.is_file():
                raise FileNotFoundError(f"Restore or rebuild processed data: {path}")
        con = duckdb.connect()
        try:
            con.execute("SET threads = 2")
            con.execute("SET memory_limit = '3GB'")
            for alias, path in paths.items():
                con.read_parquet(str(path)).create_view(alias)
        except Exception:
            con.close()
            raise
        return con

    def products(self, *, garment_group=None, product_type=None, lifecycle_profile=None,
                 momentum_tier=None, complete_only=False):
        filters = {"garment_group_name": garment_group, "product_type_name": product_type,
                   "lifecycle_profile": lifecycle_profile, "momentum_tier": momentum_tier}
        clauses, parameters = [], []
        for column, value in filters.items():
            if value is not None:
                clauses.append(f"{column} = ?")
                parameters.append(value)
        if complete_only:
            clauses.append("complete_lifecycle = 1")
        where = " AND ".join(clauses) or "TRUE"
        with self._connect() as con:
            return con.execute(f"SELECT * FROM profiles WHERE {where} ORDER BY total_units DESC, article_id", parameters).df()

    def product(self, article_id):
        with self._connect() as con:
            result = con.execute("SELECT * FROM profiles WHERE CAST(article_id AS VARCHAR) = ?", [str(article_id)]).df()
        if result.empty:
            raise KeyError(f"Article is not in the eligible population: {article_id}")
        return result.iloc[0].to_dict()

    def history(self, article_id, *, start_date=None, end_date=None):
        """Date filters trim display rows; accumulation and momentum retain full history."""
        start = date.fromisoformat(str(start_date)) if start_date is not None else None
        end = date.fromisoformat(str(end_date)) if end_date is not None else None
        if start and end and start > end:
            raise ValueError("start_date must be on or before end_date")
        self.product(article_id)
        clauses, parameters = [], [str(article_id)]
        if start:
            clauses.append("date >= ?")
            parameters.append(start)
        if end:
            clauses.append("date <= ?")
            parameters.append(end)
        where = " AND ".join(clauses) or "TRUE"
        with self._connect() as con:
            return con.execute(f"""
                WITH full_history AS (
                    SELECT article_id, date, daily_units, units_ma7, ma7_window_days,
                           valid_momentum_day, demand_velocity, demand_acceleration,
                           velocity_pct_of_typical_day, daily_velocity_percentile,
                           daily_relative_velocity_percentile,
                           SUM(daily_units) OVER (
                               ORDER BY date ROWS UNBOUNDED PRECEDING
                           ) AS cumulative_units,
                           100.0 * SUM(daily_units) OVER (
                               ORDER BY date ROWS UNBOUNDED PRECEDING
                           ) / SUM(daily_units) OVER () AS cumulative_share_pct
                    FROM momentum WHERE CAST(article_id AS VARCHAR) = ?
                ) SELECT * FROM full_history WHERE {where} ORDER BY date
            """, parameters).df()
