import test from 'node:test';
import assert from 'node:assert/strict';
import { decodeHistory, filterHistory, filterProducts, toCSV } from '../src/data.js';

function fixture() {
  const count = 15;
  const buffer = new ArrayBuffer(count * 6), view = new DataView(buffer);
  const validCounts = new Map();
  for (let i=0; i<count; i++) {
    const date = `2020-01-${String(i+1).padStart(2,'0')}`;
    validCounts.set(date, 5);
    view.setUint16(i*6, i*i, true);
    const rank = i>=4 && i<=10 ? 3 : 65535;
    view.setUint16(i*6+2,rank,true); view.setUint16(i*6+4,rank,true);
  }
  return { buffer, validCounts, profile: { article_id:'0000000001',first_sale_date:'2020-01-01',observed_lifespan_days:count,history_offset:0,total_units:1015,active_sales_days:14 } };
}

test('quadratic counts reconstruct full-window derivatives and original ranks',()=>{
  const f=fixture(), rows=decodeHistory(f.profile,f.buffer,f.validCounts);
  assert.equal(rows.length,15);
  assert.equal(rows[7].units_ma7,53);
  assert.equal(rows[7].demand_velocity,14);
  assert.ok(Math.abs(rows[7].demand_acceleration-2)<1e-12);
  assert.equal(rows[7].daily_velocity_percentile,75);
  assert.equal(rows.filter(r=>r.valid_momentum_day).length,7);
  assert.equal(rows[0].demand_velocity,null);
  assert.equal(rows.at(-1).cumulative_share_pct,100);
  assert.equal(rows[0].daily_units,0);
});

test('display filtering keeps prior accumulation and excludes no interior zeros',()=>{
  const f=fixture(), full=decodeHistory(f.profile,f.buffer,f.validCounts);
  const trimmed=filterHistory(full,'2020-01-08','2020-01-09');
  assert.deepEqual(trimmed,full.slice(7,9));
  assert.ok(trimmed[0].cumulative_units>trimmed[0].daily_units);
  assert.throws(()=>filterHistory(full,'2020-02-01','2020-01-01'));
  assert.equal(filterHistory(full,'2021-01-01','2021-01-02').length,0);
});

test('corrupt history length and totals fail instead of displaying misleading charts',()=>{
  const f=fixture();
  assert.throws(()=>decodeHistory(f.profile,new ArrayBuffer(3),f.validCounts));
  assert.throws(()=>decodeHistory({...f.profile,total_units:1},f.buffer,f.validCounts));
  new DataView(f.buffer).setUint16(2,0,true);
  assert.throws(()=>decodeHistory(f.profile,f.buffer,f.validCounts),/full-window/);
});

test('product filters preserve IDs, combine populations, and support empty matches',()=>{
  const rows=[{article_id:'0000000001',prod_name:'Test swimsuit',garment_group_name:'Swimwear',complete_lifecycle:1},
    {article_id:'0000000002',prod_name:'Other',garment_group_name:'Trousers',complete_lifecycle:0}];
  assert.deepEqual(filterProducts(rows,{search:'0000000001',complete:true}),[rows[0]]);
  assert.equal(filterProducts(rows,{group:'Swimwear',search:'OTHER'}).length,0);
  assert.deepEqual(filterProducts(rows,{search:'SWIMSUIT'}),[rows[0]]);
});

test('CSV retains string IDs, gaps, quotes, and column order',()=>{
  assert.equal(toCSV([{article_id:'0001',note:'a,"b"',velocity:null}]),'"article_id","note","velocity"\n"0001","a,""b""",');
});
