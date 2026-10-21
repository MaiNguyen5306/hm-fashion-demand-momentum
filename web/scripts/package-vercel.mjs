// Assemble Vercel's Build Output API directory. This never deploys or links a project.
import { cp, mkdir, mkdtemp, readdir, rename, rm, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const dist=path.join(root,'dist');
await stat(path.join(dist,'index.html'));
async function size(directory) {
  let total=0;
  for (const item of await readdir(directory,{withFileTypes:true})) {
    const target=path.join(directory,item.name);
    total+=item.isDirectory()?await size(target):(await stat(target)).size;
  }
  return total;
}
const bytes=await size(dist);
if (bytes>90*1024*1024) throw new Error('Build exceeds the conservative 90 MiB package budget.');
const parent=path.join(root,'.vercel');
await mkdir(parent,{recursive:true});
const temporary=await mkdtemp(path.join(parent,'.package-'));
const staged=path.join(temporary,'new'), previous=path.join(temporary,'previous'), output=path.join(parent,'output');
let hadPrevious=false;
try {
  await mkdir(staged);
  await cp(dist,path.join(staged,'static'),{recursive:true});
  await writeFile(path.join(staged,'config.json'),JSON.stringify({version:3,routes:[{src:'/data/(.*)',headers:{'Cache-Control':'public, max-age=0, must-revalidate'},continue:true}]},null,2)+'\n');
  try { await rename(output,previous); hadPrevious=true; } catch(error) { if(error.code!=='ENOENT') throw error; }
  try { await rename(staged,output); }
  catch(error) { if(hadPrevious) await rename(previous,output); throw error; }
} finally {
  // Only the staging directory created above (including the previous generated build).
  await rm(temporary,{recursive:true,force:true});
}
console.log(`Prepared local Vercel Build Output API artifact: ${output} (${(bytes/1024/1024).toFixed(2)} MiB). Nothing was deployed.`);
