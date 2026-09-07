// ---------------------------------------------------------------------------
// Robust adapter so a single Web-style handler runs on ANY Vercel Node runtime
// mode. Vercel sometimes executes a `export default` function in LEGACY Node
// mode as `(req, res) => void`, where a returned `Response` is silently
// ignored (the function then hangs until the platform timeout — exactly the
// `req.headers.get is not a function` + 300s-timeout failures seen on
// app.brandforge-os.com). It may instead run the same file in Web mode
// (`Request => Response`), or route by named HTTP-method exports.
//
// `serve(handler)` wraps a Web-style core handler and detects which mode it is
// being called in:
//   - `serve(handle)(req, res)` where `res` is a real Node ServerResponse
//     (has `end` + `setHeader`)        -> LEGACY: convert the Node
//     IncomingMessage into a Web Request, run the handler, write the Response
//     through `res`.
//   - `serve(handle)(req)` / `(req, ctx)`  -> WEB/tests: pass straight through
//     and return the Response. The 2nd argument is a route `ctx` (e.g.
//     `{ params }`), not a `res`, so it is forwarded untouched. This also
//     keeps the vitest suite working (it passes a plain `{ method }` or
//     `{ method, json }` mock and reads back `{ status, body }`).
//
// Usage per route:
//   async function handle(req, ctx) { ...existing Web-style logic... }
//   export default serve(handle);
//   export const GET = serve(handle);   // (etc. for each method the route serves)
// ---------------------------------------------------------------------------

function isNodeResponse(res) {
  return (
    res &&
    typeof res === "object" &&
    typeof res.end === "function" &&
    typeof res.setHeader === "function"
  );
}

export function toWebRequest(req) {
  // Already a genuine Web Request (has .headers.get and a body-read method).
  if (req && typeof req.headers?.get === "function" && typeof req.text === "function") {
    return req;
  }
  // Legacy IncomingMessage (or a minimal test mock): build a Web Request.
  const method = String(req?.method || "GET").toUpperCase();
  const url = typeof req?.url === "string" && req.url ? req.url : "/";
  // `new Request` requires an absolute URL; relative paths fail in Node.
  const absUrl = url.startsWith("http")
    ? url
    : "https://brandforge.local" + (url.startsWith("/") ? url : "/" + url);
  const headers = new Headers();
  const src = req?.headers || {};
  for (const k of Object.keys(src)) {
    const v = src[k];
    headers.set(k, Array.isArray(v) ? v.join(", ") : v == null ? "" : String(v));
  }
  const hasBody = method !== "GET" && method !== "HEAD";
  if (hasBody && typeof req?.on === "function") {
    // Read the request stream into the Web Request body.
    return new Promise((resolve, reject) => {
      const chunks = []; let bytes = 0, exceeded = false;
      req.on("data", (c) => {
        bytes += Buffer.byteLength(c);
        if (bytes > 1_000_000) { exceeded = true; chunks.length = 0; }
        else if (!exceeded) chunks.push(Buffer.from(c));
      });
      req.on("end", () => exceeded ? reject(Object.assign(new Error("Request too large"), {status:413})) : resolve(new Request(absUrl, { method, headers, body: Buffer.concat(chunks) })));
      req.on("error", reject);
    });
  }
  return new Request(absUrl, { method, headers, body: hasBody ? "" : undefined });
}

export async function writeResponse(webRes, res) {
  res.statusCode = webRes.status || 200;
  const h = webRes.headers;
  if (h && typeof h.forEach === "function") h.forEach((v, k) => res.setHeader(k, v));
  else if (h && typeof h.entries === "function") {
    for (const [k, v] of h.entries()) res.setHeader(k, v);
  }
  // Preserve binary/gzip responses as bytes, not lossy UTF-8 strings.
  res.end(Buffer.from(await webRes.arrayBuffer()));
}

export function serve(handler) {
  return async function (req, res) {
    if (isNodeResponse(res)) {
      try {
        const webReq = await toWebRequest(req);
        const webRes = await handler(webReq);
        return writeResponse(webRes, res);
      } catch (error) {
        return writeResponse(new Response(JSON.stringify({error:error.status===413?'Request too large':'Service temporarily unavailable'}), {status:error.status||503,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}}),res);
      }
    }
    // Web mode (named-export routing) or test harness: pass through. The 2nd
    // arg here is a route `ctx` (e.g. { params }), NOT a `res`, so forward it.
    try {
      return await handler(req, res);
    } catch (error) {
      const status=Number.isInteger(error?.status)&&error.status>=400&&error.status<=599?error.status:503;
      return new Response(JSON.stringify({error:status===413?'Request too large':'Service temporarily unavailable. Please retry.'}), {status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
    }
  };
}
