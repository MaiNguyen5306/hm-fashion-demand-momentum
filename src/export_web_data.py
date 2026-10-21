"""Create a complete static browser dataset; no raw data or Python server is shipped."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tempfile

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SHARDS = 128
NULL_RANK = 65535


def gzip_json(path, value):
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as stream:
            stream.write(json.dumps(value, separators=(',', ':'), allow_nan=False).encode())


def export_web(processed, summaries, destination, max_mb=90):
    processed, summaries, destination = Path(processed), Path(summaries), Path(destination)
    required = [processed/'product_profiles.parquet', processed/'contextual_momentum_metrics.parquet',
                summaries/'catalog_daily_momentum.csv', summaries/'garment_group_business_summary.csv']
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f'Rebuild the analysis before exporting: {path}')
    if destination.resolve() in {processed.resolve(), summaries.resolve()}:
        raise ValueError('Web output must be separate from analytical inputs.')
    profiles = pd.read_parquet(required[0]).sort_values('article_id').reset_index(drop=True)
    catalog = pd.read_csv(required[2])
    categories = pd.read_csv(required[3])
    if profiles.article_id.duplicated().any() or not profiles.article_id.astype(str).str.fullmatch(r'\d{10}').all():
        raise ValueError('Expected unique 10-digit string article IDs.')
    if len(profiles) >= NULL_RANK or catalog.valid_momentum_articles.max() >= NULL_RANK:
        raise ValueError('Population exceeds the uint16 rank encoding; increase the format version.')
    profiles['history_shard'] = profiles.article_id.map(lambda value: (int(value)//1000) % SHARDS)
    profiles['history_offset'] = profiles.groupby('history_shard').observed_lifespan_days.cumsum() - profiles.observed_lifespan_days
    id_index = pd.Index(profiles.article_id)
    first_dates = pd.to_datetime(profiles.first_sale_date).to_numpy().astype('datetime64[D]')
    profile_offsets = profiles.history_offset.to_numpy()
    units_by_article = np.zeros(len(profiles), dtype=np.float64)
    rows_by_article = np.zeros(len(profiles), dtype=np.int64)
    shard_offsets = np.zeros(SHARDS, dtype=np.int64)
    valid_counts = dict(zip(catalog.date, catalog.valid_momentum_articles))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary)/'new'
        staging.mkdir()
        streams = {}
        raw_streams = {}
        try:
            with duckdb.connect() as con:
                con.execute("SET threads=2")
                con.execute("SET memory_limit='3GB'")
                con.read_parquet(str(required[1])).create_view('momentum')
                # One ordered streaming scan; never materialize the full panel in Python.
                reader = con.execute(f"""
                    SELECT article_id,date,daily_units,valid_momentum_day,
                           daily_velocity_percentile,daily_relative_velocity_percentile,
                           (CAST(article_id AS BIGINT)//1000)%{SHARDS} AS shard
                    FROM momentum ORDER BY shard,article_id,date
                """).to_arrow_reader(batch_size=200000)
                for batch in reader:
                    frame = batch.to_pandas()
                    for shard, group in frame.groupby('shard', sort=False):
                        shard = int(shard)
                        if shard not in streams:
                            raw_streams[shard] = (staging/f'history-{shard:03d}.bin.pack').open('wb')
                            streams[shard] = gzip.GzipFile(filename='', fileobj=raw_streams[shard], mode='wb', compresslevel=6, mtime=0)
                        positions = id_index.get_indexer(group.article_id)
                        if (positions < 0).any():
                            raise ValueError('History contains an article absent from the profile table.')
                        days = np.arange(len(group)) + shard_offsets[shard] - profile_offsets[positions]
                        actual_dates = group.date.to_numpy().astype('datetime64[D]')
                        if (days < 0).any() or not np.array_equal(first_dates[positions]+days.astype('timedelta64[D]'), actual_dates):
                            raise ValueError('History order, dates, or profile offsets do not reconcile.')
                        units = group.daily_units.to_numpy()
                        if not np.isfinite(units).all() or (units < 0).any() or (units >= NULL_RANK).any() or not np.equal(units, np.floor(units)).all():
                            raise ValueError('Units cannot be encoded losslessly as uint16.')
                        valid = group.valid_momentum_day.to_numpy() == 1
                        counts = np.array([valid_counts[str(value)[:10]] for value in group.date])
                        denominators = np.maximum(counts-1, 1)
                        packed = np.full((len(group),3), NULL_RANK, dtype='<u2')
                        packed[:,0] = units.astype('<u2')
                        for column, field in enumerate(['daily_velocity_percentile','daily_relative_velocity_percentile'], 1):
                            percentiles = group[field].to_numpy()
                            if not np.isnan(percentiles[~valid]).all() or not np.isfinite(percentiles[valid]).all():
                                raise ValueError('Percentile nulls violate momentum validity.')
                            ranks = np.rint(percentiles[valid]*denominators[valid]/100)
                            if (ranks < 0).any() or (ranks >= NULL_RANK).any() or not np.allclose(100*ranks/denominators[valid], percentiles[valid], rtol=0, atol=1e-9):
                                raise ValueError('Percentile rank encoding failed round-trip validation.')
                            packed[valid,column] = ranks.astype('<u2')
                        streams[shard].write(packed.tobytes())
                        shard_offsets[shard] += len(group)
                        units_by_article += np.bincount(positions, weights=units, minlength=len(profiles))
                        rows_by_article += np.bincount(positions, minlength=len(profiles))
        finally:
            for stream in streams.values():
                stream.close()
            for stream in raw_streams.values():
                stream.close()
        if not np.array_equal(rows_by_article, profiles.observed_lifespan_days.to_numpy()) or not np.array_equal(units_by_article, profiles.total_units.to_numpy()):
            raise ValueError('Exported article histories do not reconcile to profiles.')
        if units_by_article.sum() != catalog.catalog_units.sum():
            raise ValueError('Catalog and history units do not reconcile.')
        gzip_json(staging/'profiles.json.pack', json.loads(profiles.to_json(orient='records',date_format='iso')))
        gzip_json(staging/'catalog.json.pack', json.loads(catalog.to_json(orient='records')))
        gzip_json(staging/'categories.json.pack', json.loads(categories.to_json(orient='records')))
        assets = {}
        for path in sorted(staging.iterdir()):
            assets[path.name] = {'bytes':path.stat().st_size, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        size = sum(item['bytes'] for item in assets.values())
        manifest = {
            'schema_version': 1, 'eligible_articles':len(profiles),
            'eligible_units':int(profiles.total_units.sum()), 'history_rows':int(rows_by_article.sum()),
            'history_articles':len(profiles), 'shards':SHARDS,
            'history_encoding':{'endian':'little','bytes_per_row':6,'columns':['daily_units','velocity_rank_index','relative_velocity_rank_index'],'null_rank':NULL_RANK},
            'reconstruction':'MA7 and finite differences reconstructed from complete raw daily counts; ranks decoded with same-date valid-population denominators; all dates retained',
            'peak_policy':'Earliest tied date; distinct raw/smoothed peaks',
            'catalog_scope':'Momentum-eligible articles only',
            'compressed_asset_bytes':size, 'assets':assets,
        }
        (staging/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        if sum(p.stat().st_size for p in staging.iterdir()) > max_mb*1024*1024:
            raise ValueError(f'Web export exceeds {max_mb} MiB; previous assets were not replaced.')
        previous = Path(temporary)/'previous'
        if destination.exists():
            permitted = lambda p: p.name == 'manifest.json' or p.name.startswith('history-') or p.name in {'profiles.json.gz','catalog.json.gz','categories.json.gz','profiles.json.pack','catalog.json.pack','categories.json.pack'}
            if not all(p.is_file() and permitted(p) for p in destination.iterdir()):
                raise ValueError('Output directory contains files outside the generated web dataset.')
            destination.replace(previous)
        try:
            staging.replace(destination)
        except OSError:
            if previous.exists():
                previous.replace(destination)
            raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--processed-dir',type=Path,default=ROOT/'data/processed')
    parser.add_argument('--summary-dir',type=Path,default=ROOT/'outputs')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'web/public/data')
    parser.add_argument('--max-mb',type=float,default=90)
    args=parser.parse_args()
    manifest=export_web(args.processed_dir,args.summary_dir,args.output_dir,args.max_mb)
    (ROOT/'outputs/web_data_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f"Exported {manifest['history_articles']:,} full histories ({manifest['history_rows']:,} days), {manifest['compressed_asset_bytes']/1024/1024:.2f} MiB.")


if __name__=='__main__':
    main()
