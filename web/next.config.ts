import type { NextConfig } from "next";

// Where the FastAPI backend is reachable *from the Next server process* (not
// from the browser). Local dev and Codespaces both run it on the same host.
const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Let the frontend reach the API same-origin. Setting NEXT_PUBLIC_API_URL=""
  // makes the browser request /api/... and /media/... from the Next server,
  // which forwards them here.
  //
  // This is what makes the dashboard work in a GitHub Codespace: there the
  // browser is on a forwarded *.app.github.dev host, so a direct call to
  // localhost:8000 hits the user's own machine and fails, and pointing it at
  // the forwarded API host means a cross-origin request to a second private
  // port. Proxying keeps everything on one origin and one forwarded port.
  //
  // Unset NEXT_PUBLIC_API_URL (the default) and the browser calls the backend
  // directly on localhost:8000 as before, with CORS handling the origin.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiTarget}/api/:path*` },
      { source: "/media/:path*", destination: `${apiTarget}/media/:path*` },
    ];
  },
};

export default nextConfig;
