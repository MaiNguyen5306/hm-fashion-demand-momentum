# H&M Fashion Demand Momentum

This project analyzes how fashion products gain, sustain, and lose observed demand. It separates sales level, demand momentum, and cumulative lifecycle performance using H&M transaction data from 2018-09-20 through 2020-09-22.

The analytical pipeline is implemented. The Streamlit Executive Overview uses tracked summary CSVs; Demand Momentum and Product Lifecycle Explorer pages remain planned.

## Local setup

The current local setup uses Python 3.14. Install the pinned dependencies in an isolated environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run dashboard/app.py
```

The overview needs only `outputs/`. Raw CSVs and processed Parquet files are excluded from Git to protect against accidental commits of large datasets. The `.gitkeep` placeholders preserve the data directory structure; `.gitignore` provides the protection. No raw data have been committed or pushed by the setup work.

## Restore and reproduce the analysis

Copy existing processed files to `data/processed/` when available. Otherwise obtain `articles.csv` and `transactions_train.csv` from the [H&M Kaggle competition](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data), following its access requirements, and place them in `data/raw/`. Images and customer data are not needed. Summary outputs cannot reconstruct the original product histories.

Run the full pipeline with:

```bash
.venv/bin/python src/run_pipeline.py
```

It snapshots existing CSV outputs, records raw-file SHA-256 hashes and each step's exit status and duration, and saves logs under the ignored `data/interim/pipeline_runs/` directory. It stops on the first failed step. Resume with `--start-at <filename>` only when prerequisite outputs exist. It does not roll back already completed stages after failure. The final stages enforce analytical checks, generate the compact export, and compare regenerated CSVs against the snapshot. Comparison tolerates floating-point differences of `1e-9` and ignores row order. Intended methodological changes may legitimately fail this comparison and require review.

For individual stages, use `.venv/bin/python src/<filename>` in this order. Builders write generated files and summaries; review validation results before proceeding.

1. `validate_raw_data.py`
2. `build_daily_panel.py`
3. `validate_processed_data.py`
4. `create_eda_summary.py`
5. `create_lifecycle_summary.py`
6. `profile_momentum_eligibility.py`
7. `build_momentum_panel.py`
8. `create_momentum_metrics.py`
9. `contextualize_momentum.py`
10. `analyze_catalog_surges.py`
11. `create_cumulative_lifecycle_metrics.py`
12. `create_product_profiles.py`
13. `create_category_insights.py`
14. `validate_analysis_data.py`
15. `export_dashboard_data.py`
16. `validate_product_access.py`

Reference totals in the tracked outputs are 31,788,324 units across 104,547 purchased articles. The momentum population requires at least 30 active sales days and 100 units: 44,014 articles, 29,996,706 units, and 15,380,104 continuous article-day rows. Of these articles, 31,833 pass the boundary-based complete-observed-lifecycle rule.

`validate_analysis_data.py` enforces table grains, date continuity, population/unit reconciliation, finite-difference formulas, normalization, cumulative accumulation, milestone bounds, and classification completeness. Its passing report is saved as `outputs/analysis_validation.json`. Raw and daily-panel validation scripts also raise errors when core checks fail.

The [data contract](DATA_CONTRACT.md) defines field meanings, populations, peak rules, and the local query interface. `outputs/data_schemas.json` lists actual stored field types for every processed table. `src/product_data.py` provides product filtering, metadata, and full histories for any eligible article without a web framework; date filters retain full-history accumulation and momentum.

## Prepare dashboard data

After restoring `product_profiles.parquet` and `contextual_momentum_metrics.parquet`, run:

```bash
.venv/bin/python src/export_dashboard_data.py
```

The exporter writes to the ignored `dashboard/data/` directory:

- All eligible product profiles, with `has_daily_curve` indicating curve availability.
- Complete daily histories for the five highest-volume articles per lifecycle profile, with article ID breaking selection ties. These are selected examples, not a representative sample. No time-series downsampling is applied.
- Daily momentum context for the full eligible population.
- A manifest with population counts, selection policy, interpretation notes, and artifact sizes.

It rejects duplicate article-day rows, date gaps, inconsistent totals/endpoints, and invalid momentum-window nulls. Profiles and catalog totals must reconcile to the saved validation summary. Files are prepared in staging before replacement; an export over the default 25 MiB total budget is rejected before replacement. Generated data remain ignored until their real size and content have been reviewed. The existing overview continues reading `outputs/`.

Use `--per-profile N` to expand curve coverage and `--max-mb N` to set the total budget. The first real-data export contains 44,014 profiles and 16,710 curve rows for 30 selected articles, totaling about 2.5 MiB. Full histories for all 44,014 articles remain available in the local processed Parquet files. Full-population public export size remains unmeasured; the sample export does not provide arbitrary-product curve coverage.

## Interpretation and limitations

- Transactions are observed sales, not unconstrained consumer demand; inventory and availability are unknown.
- Centered seven-day smoothing and central finite differences use future observations, up to four days ahead for momentum. Full-history scale normalization is also retrospective. These metrics describe history and do not establish live early-warning or forecasting performance.
- Relative velocity is scaled to typical active-day sales; it is not a percentage sales-growth measure.
- “Complete lifecycle” means neither exact dataset boundary is touched. First/last observed sales do not establish true launch/discontinuation dates.
- Raw daily peaks and smoothed peaks are distinct metadata fields. Ties choose the earliest date; cumulative pre/post-peak splits use the smoothed peak.
- Catalog momentum and event comparisons cover eligible articles, not the entire purchased catalog. Same-day percentiles use only valid momentum observations.
- Profile labels are descriptive rules derived from this dataset. Sustained Performer includes a high-volume condition; Extreme Momentum reflects a historical peak percentile.
- H&M prices are anonymized/scaled indices, not actual revenue. Numeric channel IDs remain unlabeled.
- Event timing does not establish causal promotion effects. Boundary months are partial months.

## Checks

```bash
.venv/bin/python -m unittest discover -s tests
```

Targeted tests cover smoothing boundaries, central differences, extrema ties, classification thresholds, export rejection, and full-history access through date filters. Synthetic fixtures stay in temporary directories and are never dashboard artifacts. Real-data validation runs separately against restored processed files.
