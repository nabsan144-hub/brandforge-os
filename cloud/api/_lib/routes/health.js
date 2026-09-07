import { serve } from "../serve.js";
// GET /api/health — zero-dependency function used to isolate whether the
// serverless function runtime is alive. No imports, no env — if this 200s but
// /api/me or /api/config don't, the problem is dependency bundling or routing;
// if it also hangs/500s, the function runtime itself isn't deploying.
async function handle() {
  return new Response(JSON.stringify({ ok: true, ts: Date.now() }), {
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

// Vercel routing adapter (dual-mode: legacy (req,res) OR Web Request->Response).
const _h = serve(handle);
export default _h;
export const GET = _h;
