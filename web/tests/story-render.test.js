import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

const root=new URL('..',import.meta.url).pathname;
let dataset;
try {
  const data=async name=>JSON.parse(gunzipSync(await readFile(new URL(`../public/data/${name}.json.pack`,import.meta.url))));
  dataset={profiles:await data('profiles'),categories:await data('categories'),manifest:JSON.parse(await readFile(new URL('../public/data/manifest.json',import.meta.url),'utf8'))};
} catch { /* Generated data are optional in a fresh clone. */ }

test('real-data story views render with correct entry points and comparison evidence',{skip:!dataset},async()=>{
  const server=await createServer({root,server:{middlewareMode:true,ws:false},appType:'custom'});
  try {
    const views=await server.ssrLoadModule('/src/story.jsx');
    const home=renderToStaticMarkup(React.createElement(views.Home,{dataset}));
    assert.match(home,/What happens afterward matters/);
    assert.match(home,/≈63/);
    for(const href of ['#/explore?question=lasting','#/explore?question=spikes','#/compare','#/categories'])assert.ok(home.includes(`href="${href}"`));
    const compare=renderToStaticMarkup(React.createElement(views.Compare,{dataset}));
    assert.match(compare,/LS Reggipetto Triangle Top/);
    assert.match(compare,/Timeless Midrise Brief/);
    assert.match(compare,/5,123/);
    assert.match(compare,/15,230/);
    assert.match(compare,/Actual sales scale/);
    const categories=renderToStaticMarkup(React.createElement(views.CategoryBars,{dataset}));
    assert.match(categories,/Swimwear/);
    assert.match(categories,/9\.73/);
  } finally {await server.close();}
});
