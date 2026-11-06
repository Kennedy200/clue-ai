const apiPort = process.env.API_PORT || "8000";

/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  poweredByHeader: false,
  // Browser talks to the API same-origin so session cookies are first-party.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `http://127.0.0.1:${apiPort}/api/:path*` }];
  },
};
