/**
 * Synthesis Lab — CORS Proxy for MUAPI.ai
 * Deploy as a Cloudflare Worker.
 *
 * All requests are forwarded to https://api.muapi.ai with CORS headers added.
 * Your API key travels from your browser → this worker → MUAPI. Nothing is logged or stored.
 *
 * Setup:
 *   1. Go to https://dash.cloudflare.com → Workers & Pages → Create
 *   2. Name it (e.g. "synthesis-proxy") → Deploy
 *   3. Click "Edit Code", paste this file, → Deploy
 *   4. Your proxy URL is: https://synthesis-proxy.<your-subdomain>.workers.dev
 *   5. In Synthesis Lab, set API Base URL to that proxy URL
 */

const TARGET = 'https://api.muapi.ai';

export default {
  async fetch(request) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(request),
      });
    }

    // Build the proxied URL
    const url = new URL(request.url);
    const target = TARGET + url.pathname + url.search;

    // Forward the request
    const headers = new Headers(request.headers);
    headers.delete('host');

    const response = await fetch(target, {
      method: request.method,
      headers,
      body: request.method !== 'GET' && request.method !== 'HEAD'
        ? request.body
        : undefined,
    });

    // Return response with CORS headers
    const proxyResponse = new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });

    for (const [k, v] of Object.entries(corsHeaders(request))) {
      proxyResponse.headers.set(k, v);
    }

    return proxyResponse;
  },
};

function corsHeaders(request) {
  return {
    'Access-Control-Allow-Origin': request.headers.get('Origin') || '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Access-Control-Max-Age': '86400',
  };
}
