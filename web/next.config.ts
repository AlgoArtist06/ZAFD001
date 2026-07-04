import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // No floating dev-tools badge: it overlapped the sidebar's "Delete account"
  // button. Compile and runtime errors still surface without it.
  devIndicators: false,
  // Proxy the FastAPI backend through this app's own origin, so the browser
  // only ever talks to one host - which lets a single tunnel (localtunnel)
  // expose the whole product. BACKEND_URL overrides where it forwards.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
