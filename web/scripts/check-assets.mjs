import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const data=path.join(root,'public/data');
let manifest;
try { manifest=JSON.parse(await readFile(path.join(data,'manifest.json'),'utf8')); }
catch { throw new Error('Web dataset is missing. From the repository root, run .venv/bin/python src/export_web_data.py, then .venv/bin/python src/validate_web_export.py.'); }
if (manifest.schema_version!==1 || manifest.history_articles!==manifest.eligible_articles) throw new Error('Unsupported or incomplete web dataset.');
let total=0;
for (const [name,asset] of Object.entries(manifest.assets)) {
  if (path.basename(name)!==name) throw new Error('Unexpected data asset path');
  const bytes=await readFile(path.join(data,name));
  if (bytes.length!==asset.bytes || createHash('sha256').update(bytes).digest('hex')!==asset.sha256) throw new Error(`Data asset integrity check failed: ${name}`);
  total+=bytes.length;
}
if (total>90*1024*1024) throw new Error('Data exceed the 90 MiB packaging budget.');
console.log(`Verified ${Object.keys(manifest.assets).length} data assets, ${(total/1024/1024).toFixed(2)} MiB.`);
