// Thin re-export so the /api/maintenance cron target stays its own small
// Vercel Function (exact-path files take precedence over the api/index.js
// dispatcher). Logic lives in _lib/routes/maintenance.js.
import h from './_lib/routes/maintenance.js';
export default h;
export const GET = h;
export const POST = h;
