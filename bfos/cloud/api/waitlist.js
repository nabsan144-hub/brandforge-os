// Thin re-export so /api/waitlist stays its own small Vercel Function and its
// CORS preflight keeps working unchanged (exact-path files take precedence
// over the api/index.js dispatcher). Logic lives in _lib/routes/waitlist.js.
import h from './_lib/routes/waitlist.js';
export default h;
export const POST = h;
export const OPTIONS = h;
