// Reproducible illustrative selection, not a representative sample of the catalog.
export function selectExamples(products) {
  const ordered = products.filter(p => Number.isFinite(p.days_to_80_pct)).slice().sort((a,b) => a.days_to_80_pct-b.days_to_80_pct || a.article_id.localeCompare(b.article_id));
  if (!ordered.length) return [];
  const chosen = [];
  for (const [quantile, label] of [[.5,'Middle-paced example'],[.15,'Faster accumulation'],[.85,'Slower accumulation']]) {
    const target = (ordered.length-1)*quantile;
    const candidates = ordered.map((product,index)=>({product,distance:Math.abs(index-target)})).sort((a,b)=>a.distance-b.distance || a.product.article_id.localeCompare(b.product.article_id));
    const available = candidates.filter(c=>!chosen.some(x=>x.product.article_id===c.product.article_id));
    const next = available.find(c=>!chosen.some(x=>x.product.prod_name===c.product.prod_name)) || available[0];
    if (next) chosen.push({product:next.product,label});
  }
  return chosen;
}
