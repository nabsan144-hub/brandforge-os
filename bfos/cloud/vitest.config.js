import {defineConfig} from 'vitest/config';
// Real PostgreSQL/WASM suites are memory-heavy. Serialize files so the tests
// are reproducible on a 2 GB developer/CI machine instead of exhausting it.
export default defineConfig({test:{maxWorkers:1,fileParallelism:false,hookTimeout:30000,testTimeout:15000}});
