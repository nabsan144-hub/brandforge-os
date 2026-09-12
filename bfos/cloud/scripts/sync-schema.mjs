import {readFileSync,readdirSync,writeFileSync} from 'node:fs';
const dir=new URL('../../supabase/migrations/',import.meta.url);
const contents='-- GENERATED from supabase/migrations. Run: node cloud/scripts/sync-schema.mjs\n\n'+readdirSync(dir).filter(f=>f.endsWith('.sql')).sort().map(f=>readFileSync(new URL(f,dir),'utf8')).join('\n\n');
const file=new URL('../schema.sql',import.meta.url);
if(process.argv.includes('--check')){if(readFileSync(file,'utf8')!==contents)throw new Error('schema.sql has drifted from migrations');}
else writeFileSync(file,contents);
