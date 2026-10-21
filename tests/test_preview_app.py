"""Local integration checks; skipped in clones without processed H&M data."""

from datetime import timedelta
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / 'data/processed/product_profiles.parquet').is_file(),
                     'Requires locally rebuilt H&M Parquet files')
class PreviewAppTests(unittest.TestCase):
    def app(self):
        return AppTest.from_file(str(ROOT / 'dashboard/preview.py')).run(timeout=30)

    def test_any_article_and_date_filter_preserve_accumulation(self):
        app = self.app()
        app.text_input[0].set_value('0372860002').run()
        self.assertFalse(app.exception)
        self.assertIn('0372860002', app.selectbox[0].options[0])
        original = app.dataframe[-1].value
        start = original.date.iloc[0].date() + timedelta(days=100)
        end = original.date.iloc[-1].date()
        app.date_input[0].set_value((start, end)).run()
        self.assertFalse(app.exception)
        trimmed = app.dataframe[-1].value
        self.assertEqual(trimmed.cumulative_units.iloc[0], original.loc[original.date.dt.date.eq(start), 'cumulative_units'].iloc[0])
        self.assertGreater(trimmed.cumulative_units.iloc[0], trimmed.daily_units.iloc[0])
        self.assertEqual(len(app.get('plotly_chart')), 3)

    def test_empty_search_and_category_selection(self):
        app = self.app()
        app.text_input[0].set_value('no-such-hm-product-xyz').run()
        self.assertFalse(app.exception)
        self.assertIn('No products match', app.info[0].value)
        app.sidebar.radio[0].set_value('Category comparison').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe), 2)
        self.assertIn('median_days_to_80_complete', app.dataframe[0].value.columns)
        app.multiselect[0].set_value([]).run()
        self.assertFalse(app.exception)
        self.assertIn('No categories', app.info[0].value)

    def test_category_filter_and_notes(self):
        app = self.app()
        app.selectbox(key='group').set_value('Swimwear').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.dataframe[0].value.garment_group_name.eq('Swimwear').all())
        app.sidebar.radio[0].set_value('Data notes').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Data scope' in text.value for text in app.subheader))


if __name__ == '__main__':
    unittest.main()
