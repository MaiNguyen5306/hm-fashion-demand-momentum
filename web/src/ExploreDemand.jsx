import React, { useEffect, useMemo, useState } from 'react';
import { loadProductHistory } from './data.js';
import { Chart, number } from './components.jsx';
import { storySentence } from './story-model.js';
import './explore-demand.css';
import { selectExamples } from './explore-examples.js';
import { EXPLORE_GROUPS, exploreGroupFor, matchesExploreGroup } from './explore-groups.js';

function ExampleCard({ product, label, selected, dataset, onChoose }) {
  const [history, setHistory] = useState(null), [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    loadProductHistory(product, dataset).then(rows => { if (active) setHistory(rows); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [product.article_id, dataset]);
  const peak = history ? Math.max(...history.map(r => r.units_ma7), 1) : 1;
  const path = history?.map((r,i) => `${i ? 'L' : 'M'}${6+i/Math.max(history.length-1,1)*288},${68-r.units_ma7/peak*58}`).join(' ');
  return <button className="explore-example" aria-pressed={selected} onClick={onChoose}>
    <span className="explore-example-label">{label}</span><strong>{product.prod_name}</strong>
    {history ? <svg viewBox="0 0 300 76" role="img" aria-label="Smoothed sales across this product’s observed history, scaled to its own peak"><path d="M6 69 H294" stroke="#e7dadd"/><path d={path} stroke="currentColor" strokeWidth="2" fill="none"/></svg> : <span className="explore-example-loading">{failed ? 'Preview unavailable · open history to retry' : 'Loading curve…'}</span>}
    <span className="explore-example-caption">80% of sales within {number(product.days_to_80_pct)} days</span>
  </button>;
}

export default function ExploreDemand({ dataset, question, article, renderDetails }) {
  const linkedProduct = dataset.profiles.find(p => p.article_id === article);
  const [directArticle, setDirectArticle] = useState(article);
  const [pattern, setPattern] = useState(linkedProduct?.lifecycle_profile === 'Rapid Spike' || (!article && question === 'spikes') ? 'spikes' : 'lasting');
  const [group, setGroup] = useState(exploreGroupFor(linkedProduct?.garment_group_name) || 'Swimwear'), [picked, setPicked] = useState(article), [view, setView] = useState('sales'), [daily, setDaily] = useState(false);
  const [history, setHistory] = useState({ id: '', rows: null, error: '' });
  const [search, setSearch] = useState('');
  const matches = useMemo(() => dataset.profiles.filter(p =>
    p.complete_lifecycle === 1 && p.lifecycle_profile === (pattern === 'spikes' ? 'Rapid Spike' : 'Sustained Performer') && matchesExploreGroup(p, group)
  ), [dataset, pattern, group]);
  const examples = useMemo(() => selectExamples(matches), [matches]);
  const searchResults = search.trim().length >= 2 ? matches.filter(p => `${p.prod_name} ${p.article_id}`.toLowerCase().includes(search.trim().toLowerCase())).slice(0,6) : [];
  const selected = (directArticle && dataset.profiles.find(p => p.article_id === directArticle)) || matches.find(p => p.article_id === picked) || examples[0]?.product || matches[0];
  useEffect(() => {
    if (!selected) return;
    let active = true;
    loadProductHistory(selected, dataset).then(rows => { if (active) setHistory({ id: selected.article_id, rows, error: '' }); }).catch(error => { if (active) setHistory({ id: selected.article_id, rows: null, error: error.message }); });
    return () => { active = false; };
  }, [selected?.article_id, dataset]);
  const rows = selected && history.id === selected.article_id ? history.rows : null;
  const error = selected && history.id === selected.article_id ? history.error : '';
  const name = selected?.article_id === '0758064001' ? 'Triangle bikini top' : selected?.article_id === '0599580017' ? 'Mid-rise bikini bottoms' : selected?.prod_name;
  const choosePattern = value => { setPattern(value); setPicked(''); setDirectArticle(''); setSearch(''); };
  const reset = () => { setGroup('Swimwear'); setPicked(''); setPattern('lasting'); setDirectArticle(''); setSearch(''); };
  return <div className="explore-demand">
    <section className="explore-intro"><span className="explore-eyebrow">Explore demand</span><h1>Every product has a story.</h1><p>Follow how sales build, peak, and accumulate. Start with a pattern, then explore a history.</p></section>
    <section className="explore-selection" aria-label="Choose a product history">
      <div className="explore-patterns" aria-label="Demand pattern">{[['lasting','What keeps selling?'],['spikes','What sells in a burst?']].map(([value,label]) => <button key={value} aria-pressed={pattern === value} onClick={() => choosePattern(value)}>{label}</button>)}</div>
      <div className="explore-find explore-group-only"><label>Garment group<select value={group} onChange={e => { setGroup(e.target.value); setPicked(''); setDirectArticle(''); setSearch(''); }}>{EXPLORE_GROUPS.map(g => <option key={g.label} value={g.label}>{g.label}</option>)}</select></label></div>
      <div className="explore-examples-heading"><h2>Choose an example</h2><span role="status">Showing {examples.length} selected examples from {number(matches.length)} matching histories.</span></div>
      <div className="explore-examples">{examples.map(({product,label}) => <ExampleCard key={product.article_id} product={product} label={label} dataset={dataset} selected={selected?.article_id === product.article_id} onChoose={() => { setPicked(product.article_id); setDirectArticle(''); }}/>)}</div>
      {examples.length > 0 && <p className="explore-examples-note">Selected by time to accumulate 80% of observed sales. Curves use each product’s own peak and history length; compare shape, not volume or duration.</p>}
      <details className="explore-search-more" key={`${pattern}-${group}`}><summary>Find another product</summary><label>Search within this pattern and garment group<input type="search" placeholder="Enter a name or article ID" value={search} onChange={e => setSearch(e.target.value)}/></label>
        {search.trim().length >= 2 && <div className="explore-search-results">{searchResults.length ? searchResults.map(p => <button key={p.article_id} onClick={() => { setPicked(p.article_id); setDirectArticle(''); }}>{p.prod_name}</button>) : <p>No matching products.</p>}<small>Up to six results. Refine the name or use an exact article ID.</small></div>}
      </details>
    </section>
    {!selected ? <section className="explore-empty"><h2>No histories found.</h2><p>Try another pattern or garment group.</p><button onClick={reset}>Clear selection</button></section> : <>
      <section className="explore-product"><div><span className="explore-eyebrow">{selected.product_type_name} · {selected.garment_group_name}</span><h2>{name}</h2><p className="explore-takeaway">{storySentence(selected)}</p></div><details className="explore-product-details"><summary>Product details</summary><p>Dataset name: {selected.prod_name}<br/>Article ID: {selected.article_id}<br/>Pattern: {selected.lifecycle_profile}</p></details></section>
      {!selected.complete_lifecycle && <p className="explore-boundary">This history reaches a dataset boundary; sales outside the available period may be missing.</p>}
      <section className="explore-chart-panel" aria-label="Product sales history">
        <div className="explore-chart-header"><div className="explore-view-switch" aria-label="Chart view">{[['sales','Sales over time'],['accumulated','Sales accumulated']].map(([value,label]) => <button key={value} aria-pressed={view === value} onClick={() => setView(value)}>{label}</button>)}</div>{view === 'sales' && <label className="explore-daily"><input type="checkbox" checked={daily} onChange={e => setDaily(e.target.checked)}/>Show daily sales</label>}</div>
        {error ? <p role="alert">{error}</p> : !rows ? <p role="status">Loading this product’s history…</p> : <Chart key={`${selected.article_id}-${view}`} interactive tooltipFields={view === 'sales' ? [{key:'units_ma7',label:'7-day average',suffix:' units/day'},{key:'daily_units',label:'Daily sales',suffix:' units'}] : [{key:'cumulative_share_pct',label:'Observed sales accumulated',suffix:'%'},{key:'cumulative_units',label:'Units sold so far',suffix:' units'}]} rows={rows} title={view === 'sales' ? 'How demand changed' : 'How sales added up'} percent={view === 'accumulated'} series={view === 'accumulated' ? [{key:'cumulative_share_pct',label:'Share of observed sales',color:'#b72e50'}] : [...(daily ? [{key:'daily_units',label:'Daily units',color:'#b8b4b5'}] : []), {key:'units_ma7',label:'7-day average · units per day',color:'#b72e50'}]}/>}
        <p className="explore-chart-note">{view === 'sales' ? 'The 7-day average smooths daily fluctuations. Its highest point marks the smoothed demand peak.' : `80% of observed sales accumulated within ${number(selected.days_to_80_pct)} days of the first observed sale.`} Calendar dates show when these sales occurred.</p>
      </section>
      <dl className="explore-key-facts"><div><dt>Total observed sales</dt><dd>{number(selected.total_units)} <small>units</small></dd></div><div><dt>Highest single-day sales</dt><dd>{number(selected.raw_peak_daily_units)} <small>units</small></dd></div><div><dt>Time to 80% of sales</dt><dd>{number(selected.days_to_80_pct)} <small>days</small></dd></div></dl>
      <div className="explore-next"><button disabled={examples.length < 2} onClick={() => { const i = examples.findIndex(x => x.product.article_id === selected.article_id); setPicked(examples[(i + 1) % examples.length].product.article_id); setDirectArticle(''); }}>Show another example <span aria-hidden="true">→</span></button><a href={`#/compare?left=${selected.article_id}`}>Compare this product ↗</a></div>
      <div className="explore-deeper" key={selected.article_id}>{renderDetails(selected)}</div>
    </>}
  </div>;
}
