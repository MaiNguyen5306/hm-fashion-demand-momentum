// Browser data contract: raw counts + lossless rank indices, never sparse selling-day sequences.
const NULL_RANK = 65535;
const DAY = 86400000;
export const dayString = (value) => String(value).slice(0, 10);
export const epochDay = (value) => Date.parse(`${dayString(value)}T00:00:00Z`) / DAY;

export function decodeHistory(profile, buffer, validCounts) {
  const count = Number(profile.observed_lifespan_days);
  const offset = Number(profile.history_offset) * 6;
  if (offset < 0 || offset + count * 6 > buffer.byteLength) throw new Error('History asset has an invalid product offset.');
  const view = new DataView(buffer);
  const units = Array.from({ length: count }, (_, i) => view.getUint16(offset + i * 6, true));
  const prefix = [0];
  units.forEach(value => prefix.push(prefix.at(-1) + value));
  if (prefix.at(-1) !== Number(profile.total_units)) throw new Error('History units do not reconcile to the product profile.');
  const windows = units.map((_, i) => Math.min(count - 1, i + 3) - Math.max(0, i - 3) + 1);
  const means = units.map((_, i) => (prefix[Math.min(count, i + 4)] - prefix[Math.max(0, i - 3)]) / windows[i]);
  const firstDay = epochDay(profile.first_sale_date);
  return units.map((daily_units, i) => {
    const date = new Date((firstDay + i) * DAY).toISOString().slice(0, 10);
    const valid = i > 0 && i + 1 < count && windows[i - 1] === 7 && windows[i] === 7 && windows[i + 1] === 7;
    const absoluteRank = view.getUint16(offset + i * 6 + 2, true);
    const relativeRank = view.getUint16(offset + i * 6 + 4, true);
    if ((valid && (absoluteRank === NULL_RANK || relativeRank === NULL_RANK)) || (!valid && (absoluteRank !== NULL_RANK || relativeRank !== NULL_RANK))) throw new Error('History ranks violate the full-window momentum rule.');
    const population = Number(validCounts.get(date));
    const denominator = Math.max(population - 1, 1);
    if (valid && (!Number.isFinite(population) || population < 1 || absoluteRank > denominator || relativeRank > denominator)) throw new Error('Invalid same-day rank population.');
    const velocity = valid ? (means[i + 1] - means[i - 1]) / 2 : null;
    const acceleration = valid ? means[i + 1] - 2 * means[i] + means[i - 1] : null;
    return { article_id: profile.article_id, date, daily_units, units_ma7: means[i], ma7_window_days: windows[i],
      valid_momentum_day: valid ? 1 : 0, demand_velocity: velocity, demand_acceleration: acceleration,
      velocity_pct_of_typical_day: valid ? 100 * velocity / (Number(profile.total_units) / Number(profile.active_sales_days)) : null,
      daily_velocity_percentile: valid ? 100 * absoluteRank / denominator : null,
      daily_relative_velocity_percentile: valid ? 100 * relativeRank / denominator : null,
      cumulative_units: prefix[i + 1], cumulative_share_pct: 100 * prefix[i + 1] / Number(profile.total_units) };
  });
}

export function filterHistory(history, start, end) {
  if (start && end && start > end) throw new Error('Start date must be on or before end date.');
  return history.filter(row => (!start || row.date >= start) && (!end || row.date <= end));
}

export function filterProducts(products, filters) {
  const term = (filters.search || '').trim().toLowerCase();
  return products.filter(p => (!filters.group || p.garment_group_name === filters.group)
    && (!filters.type || p.product_type_name === filters.type)
    && (!filters.profile || p.lifecycle_profile === filters.profile)
    && (!filters.tier || p.momentum_tier === filters.tier)
    && (!filters.complete || p.complete_lifecycle === 1)
    && (!term || `${p.article_id} ${p.prod_name}`.toLowerCase().includes(term)));
}

export function toCSV(rows) {
  if (!rows.length) return '';
  const fields = Object.keys(rows[0]);
  const quote = value => value == null ? '' : `"${String(value).replaceAll('"', '""')}"`;
  return [fields.map(quote).join(','), ...rows.map(row => fields.map(field => quote(row[field])).join(','))].join('\n');
}

export async function fetchAsset(name, manifest) {
  const response = await fetch(`/data/${name}`);
  if (!response.ok) throw new Error(`Data file unavailable (${response.status}): ${name}. Run the web data export.`);
  const bytes = await response.arrayBuffer();
  const expected = manifest.assets[name];
  if (!expected || bytes.byteLength !== expected.bytes) throw new Error(`Data asset size mismatch: ${name}`);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  const actual = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
  if (actual !== expected.sha256) throw new Error(`Data asset checksum mismatch: ${name}`);
  return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
}

export async function loadDataset() {
  const response = await fetch('/data/manifest.json', { cache: 'no-cache' });
  if (!response.ok) throw new Error('Web data are missing. Run .venv/bin/python src/export_web_data.py from the repository root.');
  const manifest = await response.json();
  if (manifest.schema_version !== 1) throw new Error('Unsupported web data version.');
  const results = await Promise.all(['profiles', 'categories', 'catalog'].map(async name => {
    const bytes = await fetchAsset(`${name}.json.pack`, manifest);
    return JSON.parse(new TextDecoder().decode(bytes));
  }));
  const [profiles, categories, catalog] = results;
  profiles.sort((a, b) => b.total_units - a.total_units || a.article_id.localeCompare(b.article_id));
  return { manifest, profiles, categories, catalog,
    validCounts: new Map(catalog.map(row => [row.date, row.valid_momentum_articles])) };
}

const shardCache = new Map();
export async function loadProductHistory(profile, dataset) {
  const name = `history-${String(profile.history_shard).padStart(3, '0')}.bin.pack`;
  if (!shardCache.has(name)) {
    if (shardCache.size >= 6) shardCache.delete(shardCache.keys().next().value);
    const promise = fetchAsset(name, dataset.manifest).catch(error => { shardCache.delete(name); throw error; });
    shardCache.set(name, promise);
  }
  return decodeHistory(profile, await shardCache.get(name), dataset.validCounts);
}
