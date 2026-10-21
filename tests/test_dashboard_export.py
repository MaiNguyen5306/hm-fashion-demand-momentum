"""Exercise export reconciliation and rejection without requiring H&M data."""

from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.export_dashboard_data import export
from src.product_data import ProductDataStore


class DashboardExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.processed, self.summaries, self.destination = root / 'processed', root / 'outputs', root / 'export'
        self.processed.mkdir()
        self.summaries.mkdir()
        profiles = pd.DataFrame({
            'article_id': [1, 2], 'lifecycle_profile': ['Rapid Spike'] * 2,
            'momentum_tier': ['High Momentum'] * 2, 'total_units': [10, 10],
            'observed_lifespan_days': [3, 3],
            'first_sale_date': ['2020-01-01'] * 2, 'last_sale_date': ['2020-01-03'] * 2,
            'garment_group_name': ['Test Group'] * 2,
            'product_type_name': ['Test Type'] * 2, 'complete_lifecycle': [1, 0],
        })
        profiles.to_parquet(self.processed / 'product_profiles.parquet')
        self.curves = pd.DataFrame({
            'article_id': [1, 1, 1, 2, 2, 2],
            'date': list(pd.date_range('2020-01-01', periods=3)) * 2,
            'daily_units': [3, 0, 7] * 2, 'units_ma7': [10 / 3] * 6,
            'valid_momentum_day': [0] * 6,
            'ma7_window_days': [3] * 6,
        })
        for column in ['demand_velocity', 'demand_acceleration', 'velocity_pct_of_typical_day',
                       'daily_velocity_percentile', 'daily_relative_velocity_percentile']:
            self.curves[column] = float('nan')
        self.save_curves()
        pd.DataFrame({'articles': [2], 'total_units': [20]}).to_csv(
            self.summaries / 'product_profile_validation.csv', index=False)
        pd.DataFrame({'date': ['2020-01-01'], 'catalog_units': [20]}).to_csv(
            self.summaries / 'catalog_daily_momentum.csv', index=False)

    def save_curves(self):
        self.curves.to_parquet(self.processed / 'contextual_momentum_metrics.parquet')

    def run_export(self, **kwargs):
        return export(self.processed, self.destination, self.summaries, per_profile=1, **kwargs)

    def test_export_keeps_zero_days_and_full_accumulation(self):
        manifest = self.run_export()
        curves = pd.read_parquet(self.destination / 'product_daily_curves.parquet')
        self.assertEqual(manifest['eligible_articles'], 2)
        self.assertEqual(curves.article_id.tolist(), [1, 1, 1])
        self.assertEqual(curves.cumulative_units.tolist(), [3, 3, 10])
        self.assertEqual(curves.cumulative_share_pct.tolist(), [30, 30, 100])
        profiles = pd.read_parquet(self.destination / 'product_profiles.parquet')
        self.assertEqual(profiles.has_daily_curve.tolist(), [True, False])

    def test_bad_totals_rejected_without_replacing_existing_export(self):
        self.run_export()
        original = (self.destination / 'manifest.json').read_bytes()
        self.curves.loc[0, 'daily_units'] = 99
        self.save_curves()
        with self.assertRaisesRegex(ValueError, 'units do not reconcile'):
            self.run_export()
        self.assertEqual((self.destination / 'manifest.json').read_bytes(), original)

    def test_gap_rejected(self):
        self.curves.loc[1, 'date'] = pd.Timestamp('2020-01-04')
        self.save_curves()
        with self.assertRaisesRegex(ValueError, 'date gaps'):
            self.run_export()

    def test_missing_valid_metrics_rejected(self):
        self.curves.loc[1, 'valid_momentum_day'] = 1
        self.save_curves()
        with self.assertRaisesRegex(ValueError, 'valid-window'):
            self.run_export()

    def test_size_budget_rejected_before_publishing(self):
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.run_export(max_mb=0.00001)
        self.assertFalse(self.destination.exists())

    def test_full_history_access_includes_product_outside_sample(self):
        self.run_export()
        store = ProductDataStore(self.processed)
        history = store.history('2', start_date='2020-01-02', end_date='2020-01-03')
        self.assertEqual(history.daily_units.tolist(), [0, 7])
        self.assertEqual(history.cumulative_units.tolist(), [3, 10])
        self.assertEqual(history.cumulative_share_pct.tolist(), [30, 100])
        self.assertEqual(len(store.products(garment_group='Test Group', complete_only=True)), 1)
        self.assertEqual(len(store.products(garment_group="' OR TRUE --")), 0)

    def test_history_rejects_unknown_article_and_reversed_dates(self):
        store = ProductDataStore(self.processed)
        with self.assertRaises(KeyError):
            store.history("missing")
        with self.assertRaises(ValueError):
            store.history('1', start_date='2020-01-03', end_date='2020-01-01')

    def test_leading_zero_identifiers_and_empty_display_range(self):
        path = self.processed / 'product_profiles.parquet'
        profiles = pd.read_parquet(path)
        profiles['article_id'] = profiles.article_id.astype(str).str.zfill(10)
        profiles.to_parquet(path)
        self.curves['article_id'] = self.curves.article_id.astype(str).str.zfill(10)
        self.save_curves()
        store = ProductDataStore(self.processed)
        self.assertEqual(store.product('0000000001')['article_id'], '0000000001')
        self.assertEqual(len(store.history('0000000001')), 3)
        self.assertTrue(store.history('0000000001', start_date='2021-01-01').empty)
        with self.assertRaises(KeyError):
            store.product('1')


if __name__ == '__main__':
    unittest.main()
