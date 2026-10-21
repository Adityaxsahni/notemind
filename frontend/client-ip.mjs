// Preloaded by the production server (`node --import ./client-ip.mjs server.js`).
//
// Next.js rewrites pass the client's own X-Forwarded-For header through to the backend
// unchanged and never add the real address. The backend trusts that header from this server
// (for per-IP rate limits), so without this a visitor could claim any address. Before Next.js
// sees a request, replace the header with the address that actually connected.
//
// Behind a load balancer that sets X-Forwarded-For itself, set TRUST_UPSTREAM_PROXY=true:
// the upstream chain is kept and the balancer's address appended (also add the balancer to
// the backend's --forwarded-allow-ips so it skips over it).
import http from "node:http";

const trustUpstream = process.env.TRUST_UPSTREAM_PROXY === "true";
const createServer = http.createServer;

http.createServer = function patchedCreateServer(...args) {
  const server = createServer.apply(this, args);
  server.prependListener("request", (req) => {
    const peer = (req.socket.remoteAddress || "").replace(/^::ffff:/, "");
    const upstream = req.headers["x-forwarded-for"];
    req.headers["x-forwarded-for"] = trustUpstream && upstream ? `${upstream}, ${peer}` : peer;
  });
  return server;
};
