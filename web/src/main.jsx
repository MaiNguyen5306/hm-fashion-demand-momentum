import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { dayString, filterHistory, filterProducts, loadDataset, loadProductHistory, toCSV } from './data.js';
import './style.css';
import ReferenceHome from './ReferenceHome.jsx';
import ExploreDemand from './ExploreDemand.jsx';

import { Chart, Download, Table, number } from './components.jsx';
import { Compare, CategoryBars, QuestionCards, QUESTIONS, storySentence } from './story.jsx';
const options = (rows, key) => [...new Set(rows.map(p => p[key]).filter(Boolean))].sort();

function Details({ profile: p, dataset }) {
  const [history, setHistory] = useState(null), [error, setError] = useState('');
  const [start, setStart] = useState(dayString(p.first_sale_date)), [end, setEnd] = useState(dayString(p.last_sale_date));
  const [tab, setTab] = useState('Demand');
  useEffect(() => {
    let active = true;
    loadProductHistory(p, dataset).then(rows => { if (active) setHistory(rows); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [p.article_id, dataset]);
  const invalidRange = start && end && start > end;
  const rows = history && !invalidRange ? filterHistory(history, start, end) : [];
  const metrics = [['Observed units', p.total_units], ['Observed span (days)', p.observed_lifespan_days], ['Selling days', p.active_sales_days],
    ['Selling-day rate (%)', p.active_day_rate_pct], ['Days to 50%', p.days_to_50_pct], ['Days to 80%', p.days_to_80_pct],
    ['Strongest 7-day share (%)', p.max_7d_demand_share_pct], ['Post-smoothed-peak share (%)', p.post_peak_share_pct]];
  return <article className="explore-technical-details">
    <details><summary>More product measures</summary><dl className="metrics">{metrics.filter((_,i) => ![0,5].includes(i)).map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{number(value)}</dd></div>)}</dl>
    <p>Raw peak: <strong>{dayString(p.raw_peak_date)}</strong> ({number(p.raw_peak_daily_units)} units). Smoothed peak: <strong>{dayString(p.smoothed_peak_date)}</strong> ({number(p.peak_smoothed_demand)} units/day). Ties use the earliest date.</p>
    <div className="controls"><label>Display from<input type="date" value={start} min={dayString(p.first_sale_date)} max={dayString(p.last_sale_date)} onChange={e => setStart(e.target.value)}/></label>
      <label>Display through<input type="date" value={end} min={dayString(p.first_sale_date)} max={dayString(p.last_sale_date)} onChange={e => setEnd(e.target.value)}/></label>
      <button onClick={() => { setStart(dayString(p.first_sale_date)); setEnd(dayString(p.last_sale_date)); }}>Full observed history</button></div>
    <p className="muted">Date filters trim display rows only. Cumulative totals, smoothing, scale denominators, and ranks retain full-history definitions. Milestone days start at day 0.</p>
    {error && <p role="alert" className="error">{error}</p>}
    {!error && !history && <p role="status">Loading and verifying this product’s history…</p>}
    {invalidRange && <p role="alert" className="error">Start date must be on or before end date.</p>}
    {history && !invalidRange && !rows.length && <p role="status">No observations in this date range.</p>}
    {rows.length > 0 && <><div className="tabs" aria-label="History view">{['Demand', 'Momentum', 'Cumulative demand', 'Daily data'].map(value => <button key={value} aria-pressed={tab === value} onClick={() => setTab(value)}>{value}</button>)}</div>
      {tab === 'Demand' && <><Chart rows={rows} title="Daily and smoothed demand" series={[{key:'daily_units',label:'Daily units',color:'#8c8c8c'},{key:'units_ma7',label:'Centered MA7',color:'#245a91'}]}/><p className="muted">Endpoint MA7 windows are truncated. The raw and smoothed peaks listed above refer to the full observed history.</p></>}
      {tab === 'Momentum' && <><p className="notice">Retrospective signals use sales up to four days ahead. These charts do not establish live forecasting performance. NULL edge values remain gaps.</p>
        <Chart rows={rows} title="Demand velocity" series={[{key:'demand_velocity',label:'Change in daily demand per elapsed day',color:'#245a91'}]}/>
        <Chart rows={rows} title="Demand acceleration" series={[{key:'demand_acceleration',label:'Second difference of daily demand',color:'#245a91'}]}/>
        <Chart rows={rows} title="Relative velocity" series={[{key:'velocity_pct_of_typical_day',label:'Scaled to typical selling-day volume; not sales growth %',color:'#245a91'}]}/>
        <Chart rows={rows} title="Same-day relative velocity percentile" percent series={[{key:'daily_relative_velocity_percentile',label:'Percentile among valid eligible products',color:'#245a91'}]}/></>}
      {tab === 'Cumulative demand' && <><Chart rows={rows} title="Accumulated share of observed demand (%)" percent series={[{key:'cumulative_share_pct',label:'Cumulative share',color:'#245a91'}]}/>
        <p>First reached 50%: <strong>{dayString(p.cumulative_50_date)}</strong>. First reached 80%: <strong>{dayString(p.cumulative_80_date)}</strong>.</p>
        <p className="muted">Accumulation uses raw units, including zero-sales dates. A filtered curve can begin above zero.</p></>}
      {tab === 'Daily data' && <><Download rows={rows} filename={`hm_${p.article_id}_${start}_${end}.csv`}>Download displayed daily rows</Download>
        <Table rows={rows} caption={`${rows.length} displayed daily observations`} fields={Object.keys(rows[0]).map(key => [key,key])}/></>}
    </>}
    </details>
  </article>;
}


function Categories({ dataset }) {
  const [group, setGroup] = useState(''), [minimum, setMinimum] = useState(100);
  const rows = dataset.categories.filter(row => (!group || row.garment_group_name === group) && row.complete_lifecycle_articles >= minimum);
  const lifecycle = [['garment_group_name','Garment group'],['complete_lifecycle_articles','Complete observed articles'],['sustained_share_complete_pct','Sustained share (%)'],['rapid_spike_share_complete_pct','Rapid-spike share (%)'],['long_tail_share_complete_pct','Long-tail share (%)'],['median_max_7d_share_complete_pct','Median strongest 7-day share (%)'],['median_days_to_80_complete','Median days to 80%']];
  const all = [['garment_group_name','Garment group'],['eligible_articles','Eligible articles'],['partial_lifecycle_articles','Partial lifecycles'],['total_units','Observed units'],['avg_units_per_article','Average units/article'],['extreme_momentum_share_pct','Extreme-momentum share (%)']];
  return <><div className="page-heading"><span className="eyebrow">Categories</span><h1>Different categories. Different demand patterns.</h1><p>Where are sustained performers more common? Where do sales arrive in a burst?</p></div><CategoryBars dataset={dataset}/><details><summary>Inspect category measures and populations</summary><p>These summaries use the full eligible population; product-browser filters do not change them.</p><div className="controls"><label>Garment group<select value={group} onChange={e => setGroup(e.target.value)}><option value="">All</option>{options(dataset.categories,'garment_group_name').map(value => <option key={value}>{value}</option>)}</select></label><label>Minimum complete observed lifecycles<input type="number" min="0" step="1" value={minimum} onChange={e => setMinimum(Math.max(0,Number(e.target.value)))}/></label></div>
    {!rows.length ? <p>No categories meet these selections.</p> : <><h3>Lifecycle metrics — complete observed lifecycles only</h3><Table rows={rows} fields={lifecycle}/><h3>Volume and momentum — all eligible products</h3><Table rows={rows} fields={all}/><Download rows={rows} filename="hm_category_summary.csv">Download selected categories</Download></>}</details>
  </>;
}

function Notes({ dataset }) {
  return <><div className="page-heading"><span className="eyebrow">About the analysis</span><h1>From purchases to demand histories.</h1><p>A retail analytics case study about sales levels, changing demand, and accumulated performance.</p></div><div className="method-steps"><section><span className="step">01</span><h3>Build the history</h3><p>Aggregate purchases into daily product sales. Keep zero-sales dates so quiet periods remain visible.</p></section><section><span className="step">02</span><h3>Understand the shape</h3><p>Smooth daily demand, measure how it changes, and compare short bursts with gradual accumulation.</p></section><section><span className="step">03</span><h3>Compare the outcomes</h3><p>Separate lifecycle shape from momentum intensity, then examine differences across garment groups.</p></section></div><h2>How to read the findings</h2><ul>
    <li>Historical observation period: September 20, 2018 through September 22, 2020.</li><li>Eligibility: at least 30 selling days and 100 units across both numeric channels.</li><li>All {number(dataset.manifest.history_articles)} eligible product histories are available, including zero-sales dates.</li><li>Complete observed lifecycles touch neither exact dataset boundary; true launch and discontinuation dates are unknown.</li><li>Raw and smoothed peaks are distinct. Ties use the earliest date; post-peak share uses the smoothed peak.</li><li>Centered momentum and whole-history normalization are retrospective. Relative velocity is not percentage sales growth.</li><li>Prices are anonymized indices. No real revenue, inventory, profit, or causal promotional effects are inferred.</li><li>Daily files are verified against exported checksums. Chart calculations retain full histories before date filters.</li></ul>
    <h3>Dataset totals</h3><dl className="metrics"><div><dt>Eligible articles</dt><dd>{number(dataset.manifest.eligible_articles)}</dd></div><div><dt>Represented units</dt><dd>{number(dataset.manifest.eligible_units)}</dd></div><div><dt>Daily observations</dt><dd>{number(dataset.manifest.history_rows)}</dd></div></dl>
    <details><summary>Web data encoding</summary><p>The static export stores raw daily units and same-day rank indices. The browser reconstructs centered MA7, finite differences, normalized velocity, and accumulation from the full daily history. Percentiles use original same-day valid-population counts. No raw transactions or customer identifiers are included.</p></details></>;
}

function readRoute() {
  const [page, query = ''] = window.location.hash.replace(/^#\/?/, '').split('?');
  return { page: page || 'home', params: new URLSearchParams(query) };
}

function App() {
  const [dataset, setDataset] = useState(null), [error, setError] = useState(''), [route, setRoute] = useState(readRoute);
  useEffect(() => { const onRoute = () => { setRoute(readRoute()); window.scrollTo(0,0); }; window.addEventListener('hashchange',onRoute); return () => window.removeEventListener('hashchange',onRoute); }, []);
  useEffect(() => { if (route.page === 'home' || dataset) return; let active = true; loadDataset().then(value => { if (active) setDataset(value); }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, [route.page, dataset]);
  if (route.page === 'home') return <ReferenceHome/>;
  const navigation = [['home','Home'],['explore','Explore demand'],['compare','Compare histories'],['categories','Categories'],['about','About the analysis']];
  return <><a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content').focus(); }}>Skip to content</a><header className="site-header"><a className="brand" href="#/home"><span className="brand-mark">H&M</span><span>Demand / Momentum<small>A retail analytics case study</small></span></a><nav aria-label="Main navigation">{navigation.map(([page,label]) => <a key={page} href={`#/${page}`} aria-current={route.page === page ? 'page' : undefined}>{label}</a>)}</nav><span className="draft-label">LOCAL DRAFT</span></header>
    <main id="main-content" tabIndex={-1}>{error ? <section role="alert"><h2>Unable to load data</h2><p>{error}</p><button onClick={() => window.location.reload()}>Retry</button></section> : !dataset ? <div className="loading-page" role="status"><span className="eyebrow">H&M demand stories</span><h1>There’s more to demand than its peak.</h1><p>Preparing the product histories…</p></div> : route.page === 'explore' ? <ExploreDemand renderDetails={profile => <Details profile={profile} dataset={dataset}/>} key={route.params.toString()} dataset={dataset} question={route.params.get('question') || 'lasting'} article={route.params.get('article') || ''}/> : route.page === 'compare' ? <Compare key={route.params.toString()} dataset={dataset} left={route.params.get('left')} right={route.params.get('right')} initialMode={route.params.get('mode') === 'cumulative' ? 'cumulative' : 'shape'}/> : route.page === 'categories' ? <Categories dataset={dataset}/> : route.page === 'about' ? <Notes dataset={dataset}/> : <section><h1>That page isn’t here.</h1><a href="#/home">Back to the story</a></section>}</main>
    <footer><span>H&M Fashion Demand Momentum</span><p>Historical observations, 2018–2020. An independent analysis of the H&M Kaggle dataset.</p><a href="#/about">Data & methodology →</a></footer></>;
}

createRoot(document.getElementById('root')).render(<App/>);
