# Local React data preview

From the repository root:

```bash
.venv/bin/python src/export_web_data.py
.venv/bin/python src/validate_web_export.py
npm --prefix web ci
npm --prefix web run dev
```

Open http://127.0.0.1:5173/#/home. Product histories are available for all eligible articles. The guided case-study draft includes a storytelling homepage, question-led exploration, a two-product comparison, category comparisons, and methodology. Final design refinement and deployment remain deferred.

Navigation uses hash URLs, so sections can be bookmarked and browser back/forward works without server routes. The homepage uses two complete observed swimwear histories: `0758064001` (Rapid Spike) and `0599580017` (Sustained Performer). Comparison offers normalized shape, cumulative share, and actual MA7 unit scales, aligned by days since first observed sale. Histories end at their actual last observed date; no trailing zero demand is invented. Headline medians are calculated from the complete-observed subset, with the population noted beside the finding.

`npm --prefix web run build` verifies assets and builds the static site. `npm --prefix web run package:vercel` prepares an offline Vercel Build Output API artifact; it does not deploy anything.

See [VERCEL_READINESS.md](../VERCEL_READINESS.md) for the architecture, complete data encoding, verification, and the generated-data requirement for future hosting.
