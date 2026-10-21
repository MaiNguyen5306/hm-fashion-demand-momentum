# Vercel migration assessment and local sample

## Decision

Use a static React/Vite website in `web/`, backed by prepared product-level assets. Keep DuckDB, Python, and Parquet for offline analysis and validation. Streamlit remains a local reference tool, not the Vercel runtime.

This avoids persistent Python servers, WebSockets, databases, and serverless queries over the raw transactions. Vercel supports static build output through its [Build Output API](https://vercel.com/docs/build-output-api). No Vercel account, project, credential, or deployment has been created by this work.

## Review of existing components

| Existing component | Vercel treatment |
|---|---|
| Raw CSVs, approximately 3.5 GB | Local analytical inputs only; remain Git-ignored |
| Python/DuckDB pipeline | Retained; no changes to eligibility, profile definitions, or analytical formulas |
| Processed Parquet files | Local source of truth; not bundled into the website |
| `ProductDataStore` | Retained for Python reference validation; not required by the browser |
| 30-example dashboard export | Retained for the older Streamlit preview; not used by the new website |
| Category and catalog CSV summaries | Converted to small prepared web assets with their existing population definitions |
| Streamlit overview and preview | Preserved; replaced by React for the Vercel-compatible sample |
| New React/Vite frontend | Static files, without a Python backend or serverless functions |

## Complete data delivery

The generated export is approximately **51.3 MiB**, covering **44,014 eligible products**, **15,380,104 daily observations**, and **29,996,706 units**. The static website build is approximately **51.6 MiB**. Export checks enforce a conservative 90 MiB budget, leaving space below Vercel Hobby's documented [100 MB CLI upload limit](https://vercel.com/docs/limits).

The full dataset is split into 128 history shards. The browser initially loads product metadata, category summaries, and catalog context, then downloads only the selected product's shard. It caches up to six shard requests. There is no 30-product coverage restriction.

Each daily record stores three little-endian unsigned 16-bit integers:

1. Raw daily units, including zeros.
2. The original same-day velocity rank index.
3. The original same-day relative-velocity rank index.

`65535` marks invalid edge ranks. Export checks reject values or populations that exceed the encoding. Article IDs remain ten-character strings. Each product's metadata stores a shard number and starting row offset; dates are implicit consecutive days from the original first observed sale. No dates are downsampled.

The browser reconstructs MA7 from the full count sequence, computes the existing central differences only on valid full windows, scales velocity using total units / active selling days, and decodes percentiles using the original same-day valid population. Cumulative sums are computed before date filtering. These are reconstructed analytical values, not a sparse approximation or a new methodology.

Files have `.pack` extensions and contain gzip data. Explicit decompression avoids local hosts or CDNs automatically interpreting `.gz` extensions and breaking checksum verification. Each compressed asset has a SHA-256 checksum and byte count in `manifest.json`; the browser verifies these before decoding. Cache headers require revalidation to avoid mixing dataset versions.

## Reproduce and view locally

From the repository root:

```bash
.venv/bin/python src/export_web_data.py
.venv/bin/python src/validate_web_export.py
npm --prefix web ci
npm --prefix web run dev
```

Open `http://127.0.0.1:5173`. Node 24 is the locally tested runtime. The Python environment uses the existing project dependencies.

The basic sample provides product search, garment/type/profile/tier filters, complete-lifecycle selection, paging, product metrics, distinct peak dates, demand/momentum/cumulative charts, display date filters, daily CSV download, category comparisons, and interpretation notes. It is for checking data and behavior; final UI/UX design is deferred.

## Build and packaging

```bash
npm --prefix web test
npm --prefix web run build
npm --prefix web run package:vercel
```

The build verifies data assets and emits `web/dist/`. Packaging prepares a local `web/.vercel/output/` directory using Build Output API version 3. Packaging does not install the Vercel CLI, link an account, register a project, or deploy anything.

For a future Vercel project, the application root is `web/`, the framework is Vite, and the output directory is `dist`. The tracked `web/vercel.json` records that configuration.

Generated assets, dependencies, builds, and `.vercel/` state stay Git-ignored. Consequently, **importing the Git repository into Vercel today will not automatically build the website**: the generated assets will be absent. The immediate future hosting path is a locally validated prebuilt artifact. A Git-based build would first need an explicit artifact-provisioning step. That decision and any deployment remain deferred; the source code does not download data from an external service.

## Verification

- Export-time reconciliation checks every product's row count, date continuity, and total units.
- Rank encoding round-trips to the stored Python percentiles within `1e-9` across all valid rows.
- `validate_web_export.py` decodes every product history with the actual JavaScript decoder, reconciles all rows and units, verifies all asset checksums, and compares five Python reference histories field by field within `1e-9`.
- Node tests cover known quadratic demand, derivative edges, cumulative filtering, corrupt assets, combined product filters, and CSV formatting.
- Python tests cover web export encoding, zero-sales dates, gaps, size limits, and preserving previous assets after validation failure.
- The local HTTP loader is checked for metadata delivery, decompression, checksum verification, and a selected product history. Browser visual review is not automated in this environment.

Reports: `outputs/web_data_manifest.json` and `outputs/web_export_validation.json`. The main pipeline now includes export and JavaScript parity validation as its final data stages.

## Remaining work

The sample is technically ready for local inspection and offline Vercel packaging. Final UI/UX, accessibility review in browsers, mobile performance review, the eventual artifact-upload process, account configuration, and deployment have not been undertaken. Hobby usage quotas still apply after any future deployment; a fitting package size is not a guarantee of unlimited free traffic.
