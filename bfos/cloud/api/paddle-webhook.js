// Thin re-export so /api/paddle-webhook stays its own small Vercel Function
// (exact-path files take precedence over the api/index.js dispatcher).
// Logic lives in _lib/routes/paddle-webhook.js.
import h from './_lib/routes/paddle-webhook.js';
export default h;
export const POST = h;
