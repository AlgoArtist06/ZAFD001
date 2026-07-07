import type { NextConfig } from "next";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const nextConfig: NextConfig = {
  // No floating dev-tools badge: it overlapped the sidebar's "Delete account"
  // button. Compile and runtime errors still surface without it.
  devIndicators: false,
  turbopack: { root: dirname(fileURLToPath(import.meta.url)) },
};

export default nextConfig;
