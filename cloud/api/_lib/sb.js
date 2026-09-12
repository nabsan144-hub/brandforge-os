// Supabase helpers for Vercel serverless functions.
import { createClient } from "@supabase/supabase-js";
import WebSocket from "ws";

export function admin({signal}={}) {
  return createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { persistSession: false },
    realtime: { transport: WebSocket },
    // Bound each SDK network request, including Storage calls whose builders
    // do not expose abortSignal. Preserve a caller's shorter operation budget.
    global: {fetch: (input,init={}) => globalThis.fetch(input,{
      ...init,signal:AbortSignal.any([init.signal,signal,AbortSignal.timeout(12000)].filter(Boolean)),
    })},
  });
}

// Validate the bearer JWT from the browser SDK; returns the auth user or null.
export async function authUser(req,{signal=req.signal}={}) {
  const h = req.headers.get("authorization") || "";
  const token = h.toLowerCase().startsWith("bearer ") ? h.slice(7).trim() : "";
  if (!token) return null;
  const { data, error } = await admin({signal}).auth.getUser(token);
  if(error&&!['400','401','403'].includes(String(error.status)))throw Object.assign(new Error('Authentication temporarily unavailable'),{status:503});
  return error ? null : data.user;
}

export function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
