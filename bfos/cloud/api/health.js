// Thin re-export so /api/health stays its own small Vercel Function (Hobby
// function-count budget: exact-path files take precedence over the catch-all
// api/index.js dispatcher). Logic lives in _lib/routes/health.js.
import h from './_lib/routes/health.js';
export default h;
export const GET = h;
