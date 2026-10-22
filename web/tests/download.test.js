import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';

test('daily download creates a CSV and clicks an anchor with the requested filename', async()=>{
  const root=new URL('..',import.meta.url).pathname;
  const server=await createServer({root,server:{middlewareMode:true,ws:false},appType:'custom'});
  const originalDocument=globalThis.document, originalCreate=URL.createObjectURL, originalRevoke=URL.revokeObjectURL;
  try {
    const {Download}=await server.ssrLoadModule('/src/components.jsx');
    let blob, clicked=false;
    const anchor={click(){clicked=true;}};
    globalThis.document={createElement(tag){assert.equal(tag,'a');return anchor;}};
    URL.createObjectURL=value=>{blob=value;return 'blob:daily-data';};
    URL.revokeObjectURL=()=>{};
    const button=Download({rows:[{date:'2020-03-24',daily_units:1}],filename:'daily.csv',children:'Download displayed daily rows'});
    button.props.onClick();
    assert.equal(clicked,true);
    assert.equal(anchor.download,'daily.csv');
    assert.equal(anchor.href,'blob:daily-data');
    assert.equal(await blob.text(), '"date","daily_units"\n"2020-03-24","1"');
    assert.equal(Download({rows:[],filename:'empty.csv'}).props.disabled,true);
  } finally {
    globalThis.document=originalDocument;
    URL.createObjectURL=originalCreate;URL.revokeObjectURL=originalRevoke;
    await server.close();
  }
});
