# Local analytical data contract — version 2

This contract defines the inputs for the future local website. No website or deployment is required to use the data. All generated daily tables remain local and Git-ignored.

## Source, population, and identifiers

The source is the H&M Kaggle competition's `articles.csv` and `transactions_train.csv`. Exact file sizes and SHA-256 hashes are in `outputs/raw_data_manifest.json`.

- Observation dates: 2018-09-20 through 2020-09-22, inclusive; 734 dates.
- Full catalog: 105,542 articles; purchased population: 104,547 articles and 31,788,324 units.
- Momentum eligibility: at least 30 distinct selling days and 100 units across both channels.
- Eligible population: 44,014 articles, 29,996,706 units, 15,380,104 article-day rows.
- Complete observed subset: 31,833 eligible articles that sell on neither exact dataset boundary. This is an operational rule, not proof of true launch/discontinuation coverage.
- `article_id` is a string identifier. Preserve its original leading zeros. `product_code` is not interchangeable with `article_id`.
- Sales-channel IDs stay numeric; no online/store mapping is asserted. Transaction duplicates represent additional purchased units and must not be deduplicated.

## Tables and relationships

All paths below are relative to `data/processed/`. `outputs/data_schemas.json` is generated from the actual Parquet schemas and lists every field's stored type, grain, and population.

| Parquet table | Grain | Population and purpose |
|---|---|---|
| `article_dimension` | Article | Full catalog; product descriptions and category attributes |
| `daily_article_sales` | Date × article × channel | All observed purchases; aggregated unit and price indices |
| `article_lifecycle` | Article | Purchased articles; observed dates, activity, raw peak, censoring |
| `momentum_daily_panel` | Article × date | Eligible articles; zero-filled histories and MA7 |
| `momentum_metrics` | Article × date | Same histories; velocity, acceleration, validity mask |
| `article_momentum_summary` | Article | Eligible articles; extrema and deterministic event dates |
| `contextual_momentum_metrics` | Article × date | Same histories; product-scale normalization and same-day ranks |
| `cumulative_lifecycle_daily` | Article × date | Same histories; cumulative demand and centered seven-day sums |
| `lifecycle_performance_summary` | Article | Eligible articles; accumulation milestones and peak splits |
| `product_profiles` | Article | Eligible articles; labels, activity, explicit peak/milestone metadata |

Article joins are many-to-one into an article-grain table. Daily tables join on both `article_id` and `date`. Do not join two daily tables by article alone. Aggregate channel rows before joining to article-day histories.

## Field interpretation

| Field or family | Meaning and rules |
|---|---|
| `units_sold`, `daily_units`, `total_units` | Counts of transaction rows; both channels combined in article-day histories |
| `avg_price_index`, `min_price_index`, `max_price_index`, `sales_value_index` | Aggregations of anonymized/scaled prices; never real currency revenue or profit |
| `first_sale_date`, `last_sale_date` | First and last observed selling dates, not true launch/discontinuation |
| `observed_lifespan_days` | Inclusive calendar span, including zero-sales dates |
| `active_sales_days` | Count of dates with positive sales, across both channels |
| `active_day_rate_pct` | 100 × active sales days / inclusive lifespan |
| `left_censored`, `right_censored` | Integer flags for touching the respective exact dataset boundary |
| `complete_lifecycle` | 1 only when both censoring flags are 0 |
| `units_ma7` | Centered mean over three preceding/current/three following dates; truncated at observed endpoints |
| `ma7_window_days` | Actual smoothing window size, 4–7 for these eligible histories |
| `valid_momentum_day` | 1 only if previous, current, and next MA7 windows each contain seven dates |
| `demand_velocity` | `(next MA7 − previous MA7) / 2`; change in daily-unit level per elapsed day |
| `demand_acceleration` | `next MA7 − 2 × current MA7 + previous MA7`; second difference of daily-unit level |
| `velocity_pct_of_typical_day` | 100 × velocity / whole-history average units per active selling day; not percentage sales growth |
| `velocity_pct_of_peak` | Secondary normalization to the observed MA7 peak; not the primary intensity ranking |
| `daily_velocity_percentile`, `daily_relative_velocity_percentile` | 100 × same-date `PERCENT_RANK`, among valid eligible observations only; ties retain equal ranks |
| `cumulative_units`, `cumulative_share_pct` | Running sum of raw daily units and percentage of full observed total |
| `cumulative_50_date`, `cumulative_80_date` | First dates meeting or exceeding the corresponding cumulative threshold |
| `days_to_50_pct`, `days_to_80_pct` | Elapsed days from first sale; first sale is day 0 |
| `rolling_7d_units`, `max_7d_units` | Centered seven-day sum and its observed maximum |
| `max_7d_demand_share_pct` | Maximum centered seven-day sum / total observed units × 100 |
| `pre_peak_units`, `peak_date_units`, `post_peak_units` | Raw units before, on, and after the **smoothed** peak date; mutually exclusive and reconcile to total units |
| `post_peak_share_pct` | Raw units strictly after the smoothed peak / total units × 100 |

Momentum fields and ranks are NULL on invalid edge dates. Do not fill those NULLs with zero. Interior zero-sales dates are valid observations and must remain in all daily curves. Peak MA7 is selected across the existing MA7 curve, including truncated endpoint windows; the full-window rule applies to derivatives, not peak selection.

## Peak and classification policy

For tied maxima or minima, select the earliest observed date. All article-level momentum extrema use this rule.

In `product_profiles`:

- `raw_peak_date` and `raw_peak_daily_units` describe the raw daily-sales peak.
- `smoothed_peak_date` and `peak_smoothed_demand` describe the MA7 peak.
- Milestone dates and both censoring flags are included explicitly.

The legacy `article_lifecycle.peak_date` means raw peak; the legacy `article_momentum_summary.peak_smoothed_demand_date` means smoothed peak. Peak-split calculations use the latter.

Lifecycle thresholds are derived from complete observed lifecycles and saved in `outputs/product_profile_thresholds.csv`. Classification precedence is Partial Lifecycle → Rapid Spike → Sustained Performer → Slow Burn → Long Tail → Balanced Lifecycle. Boundary comparisons are inclusive except Long Tail's concentration limit, which is strict. A product meeting Sustained Performer and Long Tail conditions remains a Sustained Performer.

Momentum tiers use the 25th/75th/90th percentiles of maximum **positive** relative velocity across all eligible products, not maximum absolute magnitude. The tiers and lifecycle labels are descriptive historical rules.

## Category and catalog summaries

- Category lifecycle shares and `median_max_7d_share_complete_pct` / `median_days_to_80_complete` use complete observed lifecycles only.
- Category unit totals, average units, momentum-tier shares, and average peak relative velocity use all eligible articles.
- Category standout rankings require at least 100 complete observed lifecycles. Rounded ranking ties use garment-group name ascending.
- `catalog_daily_momentum.csv` and the surge summaries cover eligible articles only.
- `observed_articles` counts articles whose observed span includes the date, even if sales are zero.
- `selling_articles` counts eligible articles with positive units on that date.
- `valid_momentum_articles` counts articles passing the full-window derivative rule. Positive-velocity share uses this denominator, not all observed or selling articles.
- Catalog averages are unweighted averages of valid article-level metrics, not derivatives of aggregate catalog units.
- The old surge-summary `active_articles` field has been replaced by the two explicit observed/selling counts. Category median field names also changed in contract version 2.

## Access without a website

```python
from src.product_data import ProductDataStore

store = ProductDataStore()
products = store.products(garment_group="Swimwear", complete_only=True)
article_id = products.iloc[0]["article_id"]
metadata = store.product(article_id)
history = store.history(article_id, start_date="2019-01-01", end_date="2019-12-31")
```

All 44,014 eligible products are accessible from local processed files. Queries return one product's daily history rather than loading the full panel into Python. Filters use bound SQL parameters. Unknown products raise `KeyError`; reversed/invalid date ranges raise `ValueError`; a valid range with no observations returns an empty frame.

Date filters apply after full-history accumulation. They do not reset cumulative units, change scale denominators, recalculate centered momentum, or rerank percentiles within the selected date range. Filters are display selections, not alternative analytical populations.

The compact `dashboard/data/` export remains a separate, disclosed example artifact: all profiles, but daily curves for only the top five articles per lifecycle label. Its `has_daily_curve` flag describes that export, not local availability or the new complete web export.

The React sample uses a separate complete static export under `web/public/data/`. It covers all eligible articles with 128 compressed binary history shards, product offsets, and original same-day valid-population counts. The browser reconstructs the same full-history MA7, finite differences, and cumulative demand before applying display date filters. Raw counts and percentile rank indices are encoded as little-endian uint16 values, with `65535` reserved for invalid edge ranks. Export checks reject out-of-range encodings; JavaScript/Python parity is checked separately. See [VERCEL_READINESS.md](VERCEL_READINESS.md) for the web contract and offline Vercel packaging strategy. Public deployment remains deferred.

## Validation and interpretation limits

Run `src/run_pipeline.py` for a logged rebuild and `python -m unittest discover -s tests` for targeted tests. `outputs/analysis_validation.json` records enforced real-data checks. `outputs/rebuild_comparison.json` detects changes against the prior snapshot; intended schema/method changes must be reviewed rather than silently accepted.

These metrics are retrospective. Centered smoothing plus finite differences can use observations four days ahead; scale normalization and classifications use whole-history information. Earlier historical momentum peaks do not establish live predictive performance. No inventory, promotion causality, true lifecycle coverage, or real revenue is inferred. The boundary months are partial months.
