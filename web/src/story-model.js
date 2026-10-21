export const EXAMPLE_IDS = ['0758064001', '0599580017'];
export const QUESTIONS = [
  {id:'lasting',title:'What keeps selling?',description:'Explore products that build demand over a longer period.',href:'#/explore?question=lasting',label:'Lasting demand'},
  {id:'spikes',title:'What sells in a burst?',description:'Follow products whose demand concentrates into a short window.',href:'#/explore?question=spikes',label:'Concentrated spikes'},
  {id:'peaks',title:'Does the bigger peak win?',description:'Put peak intensity beside accumulated performance.',href:'#/compare',label:'Peak vs. performance'},
  {id:'categories',title:'Which categories behave differently?',description:'Find where sustained performers and rapid spikes are more common.',href:'#/categories',label:'Category patterns'},
];

export function examples(profiles) {
  const rapid=profiles.find(p=>p.article_id===EXAMPLE_IDS[0]) || profiles.find(p=>p.lifecycle_profile==='Rapid Spike');
  const sustained=profiles.find(p=>p.article_id===EXAMPLE_IDS[1]) || profiles.find(p=>p.lifecycle_profile==='Sustained Performer');
  return [rapid,sustained];
}

export function median(values) {
  const sorted=values.filter(Number.isFinite).sort((a,b)=>a-b);
  if (!sorted.length) return null;
  const middle=Math.floor(sorted.length/2);
  return sorted.length%2 ? sorted[middle] : (sorted[middle-1]+sorted[middle])/2;
}

export function storySentence(p) {
  if(!p.complete_lifecycle) return 'This history reaches a dataset boundary. Explore the available sales without treating it as the product’s full lifetime.';
  if(p.lifecycle_profile==='Rapid Spike') return `Sales arrived in a concentrated burst: 80% accumulated within ${p.days_to_80_pct} days of the first observed sale.`;
  if(p.lifecycle_profile==='Sustained Performer') return `Demand built over time: reaching 80% of observed sales took ${p.days_to_80_pct} days, while its strongest week contributed ${p.max_7d_demand_share_pct}% of the total.`;
  if(p.lifecycle_profile==='Long Tail') return `${p.post_peak_share_pct}% of observed units sold after the smoothed peak. The peak was one chapter in a longer sales history.`;
  if(p.lifecycle_profile==='Slow Burn') return `Sales accumulated gradually, reaching 80% of the observed total after ${p.days_to_80_pct} days.`;
  return `Explore how ${Number(p.total_units).toLocaleString('en-US')} observed units accumulated across ${p.observed_lifespan_days} calendar days.`;
}

export function comparisonRows(left, right, mode='shape') {
  const maxLeft=Math.max(...left.map(r=>r.units_ma7)), maxRight=Math.max(...right.map(r=>r.units_ma7));
  const value=(row,peak)=>!row ? null : mode==='cumulative' ? row.cumulative_share_pct : mode==='actual' ? row.units_ma7 : (peak>0 ? 100*row.units_ma7/peak : 0);
  return Array.from({length:Math.max(left.length,right.length)},(_,i)=>({date:`Day ${i}`,left:value(left[i],maxLeft),right:value(right[i],maxRight)}));
}
