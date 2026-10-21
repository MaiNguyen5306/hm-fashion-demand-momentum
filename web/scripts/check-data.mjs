import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { gunzipSync } from 'node:zlib';
import path from 'node:path';
import assert from 'node:assert/strict';
import { decodeHistory, filterHistory } from '../src/data.js';

const [directory, referenceFile] = process.argv.slice(2);
if (!directory || !referenceFile) throw new Error('Usage: node scripts/check-data.mjs DATA_DIRECTORY REFERENCE_JSON');
const manifest = JSON.parse(await readFile(path.join(directory,'manifest.json'),'utf8'));
const json = async name => JSON.parse(gunzipSync(await readFile(path.join(directory,name))));
const profiles = await json('profiles.json.pack'), catalog = await json('catalog.json.pack');
const validCounts = new Map(catalog.map(r=>[r.date,r.valid_momentum_articles]));
const references = new Map(JSON.parse(await readFile(referenceFile,'utf8')).map(item=>[item.profile.article_id,item]));
let articles=0, rows=0, units=0, referenceRows=0;
for (const [name, asset] of Object.entries(manifest.assets)) {
  const compressed=await readFile(path.join(directory,name));
  assert.equal(compressed.length,asset.bytes,`size: ${name}`);
  assert.equal(createHash('sha256').update(compressed).digest('hex'),asset.sha256,`checksum: ${name}`);
  if (!name.startsWith('history-')) continue;
  const shard=Number(name.match(/history-(\d+)/)[1]);
  const raw=gunzipSync(compressed);
  const buffer=raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength);
  for (const profile of profiles.filter(p=>p.history_shard===shard)) {
    const history=decodeHistory(profile,buffer,validCounts);
    articles++; rows+=history.length; units+=history.at(-1).cumulative_units;
    const reference=references.get(profile.article_id);
    if (reference) {
      assert.equal(history.length,reference.rows.length);
      for (let i=0;i<history.length;i++) {
        for (const [field, expected] of Object.entries(reference.rows[i])) {
          const actual=history[i][field];
          if (expected==null || typeof expected==='string') assert.equal(actual,expected,`${profile.article_id} ${i} ${field}`);
          else assert.ok(Math.abs(actual-expected)<=1e-9,`${profile.article_id} ${i} ${field}: ${actual} != ${expected}`);
        }
      }
      const middle=history[Math.floor(history.length/2)].date;
      assert.deepEqual(filterHistory(history,middle,history.at(-1).date),history.filter(r=>r.date>=middle));
      referenceRows+=history.length;
    }
  }
}
assert.equal(articles,manifest.eligible_articles);
assert.equal(rows,manifest.history_rows);
assert.equal(units,manifest.eligible_units);
assert.ok(referenceRows>0,'No Python reference histories checked');
console.log(JSON.stringify({passed:true,articles,history_rows:rows,units,python_reference_products:references.size,python_reference_rows:referenceRows,tolerance:1e-9}));
