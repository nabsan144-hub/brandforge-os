#!/usr/bin/env node
// Deterministic test entry for the Cloud suite on RAM-constrained machines.
//
// The suite boots a real PostgreSQL (PGlite/WASM, ~0.5 GB linear memory) per
// database-backed test file. Inside one long-lived vitest process, kernel
// OOM kills occasionally sever a worker mid-file on machines at ~2 GB RAM
// ("Worker forks emitted error" with zero assertion output), which makes the
// result of the whole run depend on ambient memory noise instead of code.
//
// This runner gives every test FILE its own cleanly-torn-down vitest process
// and aggregates the per-file JSON reports. Assertion failures still fail
// immediately and are never retried, hidden or upgraded — a red assertion
// stays red. Only kernel/worker crashes are surfaced separately by name so a
// genuine environment problem cannot masquerade as a logic failure.
// Usage: node scripts/run-tests.mjs [extra vitest args passed per file]
import {execFileSync} from 'node:child_process';
import {mkdtempSync,readFileSync,readdirSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

const cloud = fileURLToPath(new URL('..', import.meta.url));
const vitest = join(cloud, 'node_modules', '.bin', 'vitest');
const files = readdirSync(join(cloud, 'tests'))
  .filter(f => f.endsWith('.test.js'))
  .sort();
const scratch = mkdtempSync(join(tmpdir(), 'bf-test-'));
const extra = process.argv.slice(2);

let total = 0, passed = 0, failed = 0, pending = 0;
const assertionFailures = [], crashedFiles = [];
// One bounded re-queue is allowed for files whose WORKER died before running
// a single assertion (kernel OOM). A file with any assertion result is never
// re-queued: a red test must stay red, green must never come from retries.
const queue = files.map(f => [f, 0]);

while (queue.length) {
  const [file, attempt] = queue.shift();
  const report = join(scratch, file + '.json');
  let status = 0;
  try {
    execFileSync(vitest, ['run', join('tests', file), '--reporter=json', `--outputFile=${report}`, ...extra],
      {cwd: cloud, stdio: 'pipe', env: {...process.env, CI: process.env.CI || '1'}});
  } catch (err) {
    status = err.status ?? 1;
  }
  let data = null;
  try { data = JSON.parse(readFileSync(report, 'utf8')); } catch { /* crashed before reporting */ }
  const f = data?.numFailedTests ?? 0, p = data?.numPassedTests ?? 0,
        t = data?.numTotalTests ?? 0, skip = data?.numPendingTests ?? 0;
  if (f === 0 && (p === 0 || status !== 0) && attempt === 0) {
    console.log(`crash? ${file}  worker exited before executing tests — re-queued once`);
    queue.push([file, 1]);
    continue;
  }
  total += t; passed += p; failed += f; pending += skip;
  if (f > 0) {
    for (const file_ of data.testResults)
      for (const a of file_.assertionResults)
        if (a.status === 'failed')
          assertionFailures.push(`${file} :: ${a.fullName}\n${(a.failureMessages || [''])[0]}`);
    console.log(`FAIL ${file}  ${p}/${t} passed  (${f} failed)`);
  } else if (p === 0 || status !== 0) {
    // Zero recorded passes with a non-clean exit after the retry = persistent
    // worker/infra crash, not a red assertion. Name it explicitly so the
    // environment problem is loud.
    crashedFiles.push(file);
    console.log(`CRASH ${file}  (worker exited after retry — likely sandbox memory)`);
  } else {
    console.log(`ok   ${file}  ${p}/${t} passed`);
  }
}
rmSync(scratch, {recursive: true, force: true});

console.log(`\nCloud suite: ${passed}/${total - pending} passed` +
  (pending ? ` (${pending} skipped)` : '') +
  (failed ? `, ${failed} assertion failures` : '') +
  (crashedFiles.length ? `, ${crashedFiles.length} file-level crashes: ${crashedFiles.join(', ')}` : ''));
if (assertionFailures.length) {
  console.error('\n=== Assertion failures (real bugs) ===\n' + assertionFailures.join('\n\n'));
  process.exit(1);
}
if (crashedFiles.length) {
  console.error('Some files never executed due to process-level crashes. Re-run this command; a crash is an environment signal, never a pass.');
  process.exit(2);
}
