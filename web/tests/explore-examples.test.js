import test from 'node:test';
import assert from 'node:assert/strict';
import { selectExamples } from '../src/explore-examples.js';
const products = Array.from({length:101},(_,i)=>({article_id:String(i).padStart(3,'0'),prod_name:`Product ${i}`,days_to_80_pct:i}));
test('examples select middle, faster and slower histories without mutating source',()=>{
  const shuffled=products.slice().reverse();
  assert.deepEqual(selectExamples(shuffled).map(x=>x.product.days_to_80_pct),[50,15,85]);
  assert.equal(shuffled[0].days_to_80_pct,100);
  assert.deepEqual(selectExamples([]),[]);
  assert.equal(selectExamples(products.slice(0,1)).length,1);
  assert.equal(new Set(selectExamples(products.slice(0,2)).map(x=>x.product.article_id)).size,2);
});
test('prefer distinct names and retain deterministic selection on ties',()=>{
  const same=products.map(p=>({...p,days_to_80_pct:1,prod_name:p.article_id==='015'?'Product 50':p.prod_name}));
  const selected=selectExamples(same);
  assert.equal(new Set(selected.map(x=>x.product.prod_name)).size,3);
  assert.deepEqual(selectExamples(same.slice().reverse()),selected);
});
