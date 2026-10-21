import React, { useEffect, useMemo, useState } from 'react';
import { loadProductHistory, dayString } from './data.js';
import { Chart, number } from './components.jsx';
import { QUESTIONS, comparisonRows, examples, median, storySentence } from './story-model.js';
export { QUESTIONS, storySentence } from './story-model.js';
const COLORS=['#b4543b','#247168'];

function useHistories(pair, dataset) {
  const ids=pair.map(p=>p?.article_id).join('|');
  const [state,setState]=useState({key:'',rows:null,error:''});
  useEffect(()=>{
    let active=true;
    if(pair.some(p=>!p)) { setState({key:ids,rows:null,error:'The selected example is unavailable.'}); return; }
    Promise.all(pair.map(p=>loadProductHistory(p,dataset))).then(rows=>{if(active)setState({key:ids,rows,error:''});}).catch(error=>{if(active)setState({key:ids,rows:null,error:error.message});});
    return ()=>{active=false;};
  },[ids,dataset]);
  return state.key===ids ? state : {rows:null,error:''};
}

function Spark({ rows, color, maxDays }) {
  const width=480,height=110,pad=8,peak=Math.max(...rows.map(r=>r.units_ma7));
  const path=rows.map((r,i)=>`${i===0?'M':'L'}${pad+i/Math.max(maxDays-1,1)*(width-2*pad)},${height-pad-(peak>0?r.units_ma7/peak:0)*(height-2*pad)}`).join(' ');
  return <svg className="spark" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Smoothed demand scaled to this product’s own peak, aligned by days since first observed sale"><line x1={pad} y1={height-pad} x2={width-pad} y2={height-pad} stroke="#d8d4ca"/><path d={`${path} L${pad+(rows.length-1)/Math.max(maxDays-1,1)*(width-2*pad)},${height-pad} L${pad},${height-pad} Z`} fill={color} opacity=".08"/><path d={path} fill="none" stroke={color} strokeWidth="2.5"/></svg>;
}

export function QuestionCards({compact=false}) {
  return <div className={compact?'question-links':'question-grid'}>{QUESTIONS.map((q,i)=><a href={q.href} className="question-card" key={q.id}>{!compact&&<span className="question-number">0{i+1}</span>}<h3>{q.title}<span aria-hidden="true"> ↗</span></h3>{!compact&&<p>{q.description}</p>}</a>)}</div>;
}

export function Home({dataset}) {
  const pair=useMemo(()=>examples(dataset.profiles),[dataset]);
  const {rows,error}=useHistories(pair,dataset);
  const complete=useMemo(()=>dataset.profiles.filter(p=>p.complete_lifecycle===1),[dataset]);
  const postPeak=useMemo(()=>median(complete.map(p=>p.post_peak_share_pct)),[complete]);
  const days80=useMemo(()=>median(complete.map(p=>p.days_to_80_pct)),[complete]);
  const topCategory=useMemo(()=>dataset.categories.filter(p=>p.complete_lifecycle_articles>=100).sort((a,b)=>b.sustained_share_complete_pct-a.sustained_share_complete_pct)[0],[dataset]);
  return <>
    <section className="hero"><div className="hero-copy"><span className="eyebrow">The life of fashion demand</span><h1>A sales spike gets attention.<br/><em>What happens afterward matters.</em></h1><p className="lede">Some products sell in a burst. Others keep building demand. Explore the histories behind the peaks—and discover what lasting performance looks like.</p><div className="hero-actions"><a className="button primary" href="#/explore?question=lasting">Explore what lasts <span>→</span></a><a className="text-link" href="#/compare">Compare two histories ↗</a></div><p className="hero-footnote">An independent case study using historical H&M purchases.</p></div>
      <div className="hero-evidence"><div className="evidence-heading"><span className="eyebrow">Two real swimwear articles</span><span className="live-dot">Observed demand</span></div><h2>A burst. A longer build.</h2>{error?<p role="alert">{error}</p>:!rows?<p role="status">Loading the two histories…</p>:pair.map((p,i)=><div className="mini-history" key={p.article_id}><div className="mini-label"><strong style={{color:COLORS[i]}}>{i===0?'Sales concentrated quickly':'Sales accumulated gradually'}</strong><span>{p.prod_name}</span></div><Spark rows={rows[i]} color={COLORS[i]} maxDays={Math.max(...rows.map(r=>r.length))}/></div>)}<div className="spark-axis"><span>First observed sale</span><span>Days afterward →</span></div><p className="chart-note">Each curve is scaled to its own smoothed peak. The same horizontal scale shows elapsed days; these curves compare shape, not sales volume.</p><a href="#/compare" className="text-link">See which sold more overall →</a></div>
    </section>
    <section className="scope-strip" aria-label="Analysis scope"><p><strong>31.8 million</strong> purchases across the source catalog.</p><span aria-hidden="true">/</span><p><strong>{number(dataset.manifest.eligible_articles)}</strong> eligible product histories explored in detail.</p></section>
    <section className="chapter-intro"><span className="eyebrow">Look beyond the highest point</span><h2>Demand has a shape.<br/>Performance has a history.</h2><p>A total tells you how much sold. A history reveals when it sold, how concentrated it was, and what continued after the peak.</p></section>
    <section className="discovery-grid"><div className="discovery feature-discovery"><span className="eyebrow">01 / The peak is only part of the story</span><p className="big-fact">≈{Math.round(postPeak)}<span>%</span></p><h3>Demand often keeps accumulating after the peak.</h3><p>For the median complete observed lifecycle, about {Math.round(postPeak)}% of units sold after the smoothed demand peak.</p><a href="#/compare?mode=cumulative" className="text-link">Follow the accumulation →</a><small>Median of article-level post-peak shares; eligible, complete observed lifecycles only.</small></div>
      <div className="discovery"><span className="eyebrow">02 / Fast is not the same as lasting</span><p className="fact-line">{number(days80)} <span>days</span></p><h3>Sales build at different speeds.</h3><p>The median complete observed lifecycle took {number(days80)} days from its first sale to accumulate 80% of its observed units. Individual histories can look very different.</p><a href="#/explore?question=spikes" className="text-link">Find the short bursts →</a></div>
      <div className="discovery"><span className="eyebrow">03 / Categories have different patterns</span><p className="fact-line category-fact">{topCategory?.garment_group_name}</p><h3>Where is sustained demand more common?</h3><p>{topCategory?.garment_group_name} has the highest Sustained Performer share among garment groups with at least 100 complete observed lifecycles.</p><a href="#/categories" className="text-link">Compare the categories →</a></div></section>
    <section className="question-section"><div className="section-heading"><div><span className="eyebrow">Choose a question, follow the evidence</span><h2>What would you like to understand?</h2></div><p>Start with an example. Then explore the products and patterns for yourself.</p></div><QuestionCards/></section>
    <section className="about-teaser"><div><span className="eyebrow">Behind the findings</span><h2>From transactions<br/>to a story of demand.</h2></div><div><p>This project separates how much products sell, how demand changes, and how sales accumulate across their observed histories. It uses H&M transaction data from 2018–2020 to investigate differences that totals alone can hide.</p><p className="muted">Observed lifecycles are not necessarily true product lifetimes. Momentum is retrospective; the analysis does not claim forecasting performance.</p><a href="#/about" className="text-link">See how the analysis works →</a></div></section>
  </>;
}

function ProductPicker({dataset,selected,onChange,exclude,label}) {
  const [search,setSearch]=useState('');
  const matches=dataset.profiles.filter(p=>p.article_id!==exclude && `${p.article_id} ${p.prod_name}`.toLowerCase().includes(search.toLowerCase())).slice(0,40);
  const choices=[selected,...matches.filter(p=>p.article_id!==selected.article_id)];
  return <details className="picker"><summary>Change {label.toLowerCase()}</summary><label>Search article ID or name<input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search all eligible articles"/></label><label>{label}<select value={selected.article_id} onChange={e=>onChange(e.target.value)}>{choices.map(p=><option key={p.article_id} value={p.article_id}>{p.article_id} · {p.prod_name}</option>)}</select></label><small>Showing up to 40 search matches plus the current selection. Search an exact ID to find any eligible article.</small></details>;
}

export function Compare({dataset,left,right,initialMode='shape'}) {
  const defaults=examples(dataset.profiles);
  const [leftId,setLeft]=useState(left || defaults[0].article_id),[rightId,setRight]=useState(right || defaults[1].article_id),[mode,setMode]=useState(initialMode);
  const a=dataset.profiles.find(p=>p.article_id===leftId)||defaults[0];
  let b=dataset.profiles.find(p=>p.article_id===rightId)||defaults[1];
  if(a.article_id===b.article_id)b=dataset.profiles.find(p=>p.article_id!==a.article_id&&p.lifecycle_profile==='Sustained Performer')||defaults[0];
  const pair=[a,b],{rows,error}=useHistories(pair,dataset);
  const chartRows=rows?comparisonRows(rows[0],rows[1],mode):[];
  const title=mode==='shape'?'How the demand shapes differ':mode==='cumulative'?'How quickly observed sales accumulated':'Smoothed daily demand on the same unit scale';
  return <><div className="page-heading"><span className="eyebrow">Compare histories</span><h1>A bigger peak.<br/><em>A better performance?</em></h1><p>Compare two observed histories. Separate the shape of demand from how much sold overall.</p></div><div className="comparison-cards">{pair.map((p,i)=><section className="comparison-card" key={i} style={{'--product-color':COLORS[i]}}><span className="eyebrow">Product {i===0?'A':'B'} / {p.lifecycle_profile}</span><h2>{p.prod_name}</h2><p className="muted">{p.garment_group_name} · {p.article_id}</p><dl className="compare-metrics"><div><dt>Highest daily sales</dt><dd>{number(p.raw_peak_daily_units)} <small>units</small></dd></div><div><dt>Total observed sales</dt><dd>{number(p.total_units)} <small>units</small></dd></div><div><dt>Time to 80% of sales</dt><dd>{number(p.days_to_80_pct)} <small>days</small></dd></div></dl><ProductPicker dataset={dataset} selected={p} exclude={pair[1-i].article_id} label={`Product ${i===0?'A':'B'}`} onChange={i===0?setLeft:setRight}/><a href={`#/explore?article=${p.article_id}`} className="text-link">Explore this history →</a></section>)}</div>
    {(!a.complete_lifecycle||!b.complete_lifecycle)&&<p className="notice">At least one history touches a dataset boundary. These are observed totals; true lifetime demand may extend beyond the available dates.</p>}
    <div className="tabs" aria-label="Comparison measure">{[['shape','Demand shape'],['cumulative','Accumulated demand'],['actual','Actual sales scale']].map(([value,label])=><button key={value} aria-pressed={mode===value} onClick={()=>setMode(value)}>{label}</button>)}</div><p className="muted">{mode==='shape'?'Each curve is scaled to its own MA7 peak (100%). Compare timing and shape, not absolute volume.':mode==='cumulative'?'Each curve shows the share of that article’s full observed units accumulated by each day.':'Both curves use actual MA7 units per day on one shared vertical scale.'} Time is aligned to each article’s first observed sale (day 0), not the same calendar date. Different historical seasons and product attributes can affect these examples.</p>
    {error?<p role="alert">{error}</p>:!rows?<p role="status">Loading both product histories…</p>:<Chart rows={chartRows} title={title} percent={mode!=='actual'} series={pair.map((p,i)=>({key:i===0?'left':'right',label:p.prod_name,color:COLORS[i]}))}/>}
    <section className="interpretation"><span className="eyebrow">Read the comparison</span><h2>{a.raw_peak_daily_units>b.raw_peak_daily_units&&a.total_units<b.total_units?'The higher daily peak did not produce the larger observed total.':b.raw_peak_daily_units>a.raw_peak_daily_units&&b.total_units<a.total_units?'The higher daily peak did not produce the larger observed total.':'Peak intensity and accumulated sales describe different things.'}</h2><p>{storySentence(a)}</p><p>{storySentence(b)}</p><small>Selected examples illustrate demand patterns; they do not establish a causal effect or represent all products.</small></section></>;
}

export function CategoryBars({dataset}) {
  const [behavior,setBehavior]=useState('sustained');
  const key=behavior==='sustained'?'sustained_share_complete_pct':behavior==='spikes'?'rapid_spike_share_complete_pct':'extreme_momentum_share_pct';
  const rows=dataset.categories.filter(p=>p.complete_lifecycle_articles>=100).sort((a,b)=>b[key]-a[key]||a.garment_group_name.localeCompare(b.garment_group_name)).slice(0,7);
  const max=Math.max(...rows.map(r=>r[key]),1);
  return <section className="category-chart"><div className="tabs" aria-label="Category question">{[['sustained','Where is sustained demand more common?'],['spikes','Where are short bursts more common?'],['momentum','Where is momentum most intense?']].map(([value,label])=><button key={value} aria-pressed={behavior===value} onClick={()=>setBehavior(value)}>{label}</button>)}</div><p className="muted">{behavior==='momentum'?'Share of all eligible articles classified as Extreme Momentum.':'Share of complete observed lifecycles with the selected lifecycle profile.'} Only garment groups with at least 100 complete observed lifecycles are shown; top seven ranked.</p><div className="bar-list">{rows.map(row=><div className="category-row" key={row.garment_group_name}><span>{row.garment_group_name}</span><div className="bar-track"><div style={{width:`${row[key]/max*100}%`}}/></div><strong>{number(row[key])}%</strong><small>{number(behavior==='momentum'?row.eligible_articles:row.complete_lifecycle_articles)} articles</small></div>)}</div><p className="chart-note">Bar lengths are relative to the largest displayed share. Each category includes varied product histories; its ranking does not describe every article.</p></section>;
}
