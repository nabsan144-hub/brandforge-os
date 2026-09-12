import {defineConfig} from 'vitest/config';
import {fileURLToPath} from 'node:url';
// Real PostgreSQL/WASM suites are memory-heavy. Serialize files so the tests
// are reproducible on a 2 GB developer/CI machine instead of exhausting it.
export default defineConfig({publicDir:false,resolve:{alias:Object.fromEntries(['vector-quality.js','visual-review.js','vendor/fflate.mjs'].map(p=>['/'+p,fileURLToPath(new URL('./public/'+p,import.meta.url))]))},root:fileURLToPath(new URL('.',import.meta.url)),test:{maxWorkers:1,fileParallelism:false,hookTimeout:30000,testTimeout:15000}});
