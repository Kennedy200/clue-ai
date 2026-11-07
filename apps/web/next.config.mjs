const apiPort = process.env.API_PORT || "8000";
const apiHost = process.env.API_HOST || "127.0.0.1"; // "api" inside Docker (read at build time)
const dev = process.env.NODE_ENV !== "production";
const https = (process.env.SITE_URL || "").startsWith("https");

// Next needs inline bootstrap scripts; everything else is locked to our own origin.
const CSP = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://upload.wikimedia.org https://*.wikimedia.org https://image.pollinations.ai",
  "media-src 'self' blob:",
  "font-src 'self' data:",
  `connect-src 'self'${dev ? " ws: wss:" : ""}`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

/** @type {import('next').NextConfig} */
export default {
  distDir: process.env.NEXT_DIST_DIR || ".next",
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  reactStrictMode: true,
  poweredByHeader: false,
  compress: true,
  // Browser talks to the API same-origin so session cookies are first-party.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `http://${apiHost}:${apiPort}/api/:path*` }];
  },
  async headers() {
    const h = [
      { key: "Content-Security-Policy", value: CSP },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
    ];
    if (https) h.push({ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" });
    return [{ source: "/:path*", headers: h }];
  },
};
