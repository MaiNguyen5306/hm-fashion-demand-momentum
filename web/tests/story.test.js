import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import { comparisonRows, median, examples, QUESTIONS, storySentence } from '../src/story-model.js';

test('comparison aligns elapsed days, normalizes each peak, and does not invent trailing sales',()=>{
  const left=[{units_ma7:2,cumulative_share_pct:20},{units_ma7:4,cumulative_share_pct:100}];
  const right=[{units_ma7:8,cumulative_share_pct:10},{units_ma7:16,cumulative_share_pct:80},{units_ma7:10,cumulative_share_pct:100}];
  const shape=comparisonRows(left,right,'shape');
  assert.deepEqual(shape.map(r=>r.left),[50,100,null]);
  assert.deepEqual(shape.map(r=>r.right),[50,100,62.5]);
  assert.equal(shape[2].date,'Day 2');
  assert.equal(comparisonRows(left,right,'actual')[0].right,8);
  assert.equal(comparisonRows(left,right,'cumulative')[1].left,100);
});

test('median excludes missing values and does not mutate the input',()=>{
  const values=[70,null,40,60,80,NaN];
  assert.equal(median(values),65);
  assert.equal(values[0],70);
  assert.equal(median([]),null);
});

test('all question paths have an actual destination and partial histories are qualified',()=>{
  assert.deepEqual(QUESTIONS.map(q=>q.href),['#/explore?question=lasting','#/explore?question=spikes','#/compare','#/categories']);
  assert.match(storySentence({complete_lifecycle:0}),/dataset boundary/);
});

const path=new URL('../public/data/profiles.json.pack',import.meta.url);
let profiles;
try { profiles=JSON.parse(gunzipSync(await readFile(path))); } catch { /* Fresh clones can run pure tests. */ }
test('real homepage examples support the peak-versus-total story', {skip:!profiles},()=>{
  const [rapid,sustained]=examples(profiles);
  assert.equal(rapid.garment_group_name,sustained.garment_group_name);
  assert.equal(rapid.complete_lifecycle,1);
  assert.equal(sustained.complete_lifecycle,1);
  assert.ok(rapid.raw_peak_daily_units>sustained.raw_peak_daily_units);
  assert.ok(rapid.total_units<sustained.total_units);
  assert.equal(rapid.lifecycle_profile,'Rapid Spike');
  assert.equal(sustained.lifecycle_profile,'Sustained Performer');
  assert.equal(Math.round(median(profiles.filter(p=>p.complete_lifecycle===1).map(p=>p.post_peak_share_pct))),63);
});
