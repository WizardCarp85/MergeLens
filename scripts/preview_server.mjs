#!/usr/bin/env node
/**
 * Platform preview shim — NOT part of mergelens.
 *
 * Serves the static dashboard export (web/out) the same way the FastAPI sidecar
 * will in step 7, plus a trivial /api/health so the hosted preview's healthcheck
 * passes. It holds no state, talks to no database and has no write endpoints.
 * Every other /api/* request answers 503 so the dashboard renders its
 * "sidecar not running" panel instead of an HTML 404.
 *
 * The real `mergelens ui` binds 127.0.0.1 only and is token-protected.
 */
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "web", "out");
const PORT = Number(process.env.PORT ?? 3000);
const HOST = process.env.HOST ?? "0.0.0.0";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".map": "application/json",
  ".webmanifest": "application/manifest+json",
};

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
    "cache-control": "no-store",
  });
  res.end(body);
}

async function fileIfExists(p) {
  try {
    const s = await stat(p);
    return s.isFile() ? p : null;
  } catch {
    return null;
  }
}

/** Resolve a request path to a file inside OUT, mirroring Next's trailingSlash export. */
async function resolveFile(urlPath) {
  const clean = path.normalize(decodeURIComponent(urlPath)).replace(/^(\.\.[/\\])+/, "");
  const abs = path.join(OUT, clean);
  if (!abs.startsWith(OUT)) return null;
  const candidates = clean.endsWith("/")
    ? [path.join(abs, "index.html")]
    : [abs, `${abs}.html`, path.join(abs, "index.html")];
  for (const c of candidates) {
    const hit = await fileIfExists(c);
    if (hit) return hit;
  }
  return null;
}

function sendFile(res, file, status = 200) {
  const type = MIME[path.extname(file)] ?? "application/octet-stream";
  const immutable = file.includes(`${path.sep}_next${path.sep}static${path.sep}`);
  res.writeHead(status, {
    "content-type": type,
    "cache-control": immutable ? "public, max-age=31536000, immutable" : "no-cache",
  });
  createReadStream(file).pipe(res);
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", "http://localhost");

  if (url.pathname === "/api/health") {
    return sendJson(res, 200, { ok: true, service: "mergelens-preview", static: OUT });
  }
  if (url.pathname.startsWith("/api/")) {
    return sendJson(res, 503, {
      detail: "mergelens sidecar not running — this is the static preview. Run `mergelens ui`.",
    });
  }
  if (req.method !== "GET" && req.method !== "HEAD") {
    return sendJson(res, 405, { detail: "method not allowed" });
  }

  const file = await resolveFile(url.pathname);
  if (file) return sendFile(res, file);

  const notFound = await fileIfExists(path.join(OUT, "404.html"));
  if (notFound) return sendFile(res, notFound, 404);
  return sendJson(res, 404, {
    detail: `not found. Is the dashboard built? Expected files under ${OUT} (run: npm run build)`,
  });
});

server.listen(PORT, HOST, () => {
  console.log(`mergelens preview: serving ${OUT} on http://${HOST}:${PORT}`);
});
