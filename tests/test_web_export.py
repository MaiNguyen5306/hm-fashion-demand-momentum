"""Verify static web artifacts reject corruption and preserve all article histories."""

import gzip
import json
from pathlib import Path
import struct
import tempfile
import unittest

import pandas as pd

from src.export_web_data import export_web


class WebExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root=Path(self.temporary.name)
        self.processed,self.summaries,self.output=root/'processed',root/'outputs',root/'web'
        self.processed.mkdir(); self.summaries.mkdir()
        self.profiles=pd.DataFrame({'article_id':['0000000001','0000000002'],
                                    'first_sale_date':['2020-01-01']*2,
                                    'observed_lifespan_days':[3,3], 'total_units':[10,10]})
        self.profiles.to_parquet(self.processed/'product_profiles.parquet')
        self.history=pd.DataFrame({'article_id':['0000000001']*3+['0000000002']*3,
                                   'date':list(pd.date_range('2020-01-01',periods=3))*2,
                                   'daily_units':[3,0,7]*2,'valid_momentum_day':[0]*6,
                                   'daily_velocity_percentile':[float('nan')]*6,
                                   'daily_relative_velocity_percentile':[float('nan')]*6})
        self.save_history()
        pd.DataFrame({'date':['2020-01-01','2020-01-02','2020-01-03'],
                      'catalog_units':[6,0,14],'valid_momentum_articles':[0]*3}).to_csv(self.summaries/'catalog_daily_momentum.csv',index=False)
        pd.DataFrame({'garment_group_name':['Test'],'eligible_articles':[2]}).to_csv(self.summaries/'garment_group_business_summary.csv',index=False)

    def save_history(self):
        self.history.to_parquet(self.processed/'contextual_momentum_metrics.parquet')

    def run_export(self,**kwargs):
        return export_web(self.processed,self.summaries,self.output,**kwargs)

    def test_all_histories_and_zero_dates_are_encoded(self):
        manifest=self.run_export()
        self.assertEqual(manifest['history_articles'],2)
        self.assertEqual(manifest['history_rows'],6)
        raw=gzip.decompress((self.output/'history-000.bin.pack').read_bytes())
        self.assertEqual(struct.unpack('<'+'H'*18,raw),(3,65535,65535,0,65535,65535,7,65535,65535)*2)
        profiles=json.loads(gzip.decompress((self.output/'profiles.json.pack').read_bytes()))
        self.assertEqual([p['history_offset'] for p in profiles],[0,3])
        self.assertEqual(profiles[0]['article_id'],'0000000001')

    def test_corrupt_totals_do_not_replace_previous_export(self):
        self.run_export(); original=(self.output/'manifest.json').read_bytes()
        self.history.loc[0,'daily_units']=99; self.save_history()
        with self.assertRaisesRegex(ValueError,'reconcile'):
            self.run_export()
        self.assertEqual((self.output/'manifest.json').read_bytes(),original)

    def test_date_gaps_and_size_budget_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'budget|exceeds'):
            self.run_export(max_mb=0.00001)
        self.assertFalse(self.output.exists())
        self.history.loc[1,'date']=pd.Timestamp('2020-01-05'); self.save_history()
        with self.assertRaisesRegex(ValueError,'dates|offsets'):
            self.run_export()


if __name__=='__main__':
    unittest.main()
