import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { selectExamples } from '../src/explore-examples.js';

const root=new URL('..',import.meta.url).pathname;

test('reference homepage renders live copy and working navigation without analytical data', async()=>{
  const server=await createServer({root,server:{middlewareMode:true,ws:false},appType:'custom'});
  try {
    const {default:ReferenceHome}=await server.ssrLoadModule('/src/ReferenceHome.jsx');
    const markup=renderToStaticMarkup(React.createElement(ReferenceHome));
    assert.match(markup,/Demand,/);
    assert.match(markup,/beyond the peak\./);
    assert.match(markup,/\/art\/home-reference\.png/);
    for(const href of ['#/home','#/explore','#/compare','#/categories','#/about','#/explore?question=lasting'])assert.ok(markup.includes(`href="${href}"`));
    assert.ok(!markup.includes('scope-strip'));
    assert.ok(markup.includes('63%'));
    assert.ok(!markup.includes('≈63%'));
    assert.ok(markup.includes('Illustrative curve')); 
    assert.equal((markup.match(/<h1 /g)||[]).length,1);
  } finally {await server.close();}
});
let dataset;
try {
  const data=async name=>JSON.parse(gunzipSync(await readFile(new URL(`../public/data/${name}.json.pack`,import.meta.url))));
  dataset={profiles:await data('profiles'),categories:await data('categories'),manifest:JSON.parse(await readFile(new URL('../public/data/manifest.json',import.meta.url),'utf8'))};
} catch { /* Generated data are optional in a fresh clone. */ }

test('simplified explorer selects the requested pattern and preserves deep links', {skip:!dataset}, async()=>{
  const server=await createServer({root,server:{middlewareMode:true,ws:false},appType:'custom'});
  try {
    const {default:ExploreDemand}=await server.ssrLoadModule('/src/ExploreDemand.jsx');
    const render=props=>renderToStaticMarkup(React.createElement(ExploreDemand,{dataset,renderDetails:()=>null,...props}));
    const burst=render({question:'spikes'});
    const expected=selectExamples(dataset.profiles.filter(p=>p.garment_group_name==='Swimwear'&&p.complete_lifecycle===1&&p.lifecycle_profile==='Rapid Spike'));
    assert.ok(burst.includes(`#/compare?left=${expected[0].product.article_id}`));
    assert.match(burst,/Sales accumulated/);
    assert.ok(!burst.includes('Look closer at the data'));
    assert.ok(!burst.includes('All histories'));
    assert.ok(!burst.includes('Choose a product<select'));
    assert.match(burst,/Choose an example/);
    assert.match(burst,/Find another product/);
    assert.equal((burst.match(/class="explore-example"/g)||[]).length,3);
    for(const example of expected) assert.ok(burst.includes(example.product.prod_name.replaceAll('&','&amp;')));
    const lasting=render({question:'lasting'});
    assert.equal((lasting.match(/class="explore-example"/g)||[]).length,3);
    const linked=render({question:'lasting',article:'0758064001'});
    assert.match(linked,/Triangle bikini top/);
  } finally {await server.close();}
});

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
