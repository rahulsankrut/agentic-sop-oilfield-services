import type { NextConfig } from "next";

/**
 * `output: "standalone"` produces a minimal Node server in `.next/standalone/`
 * — used by the Dockerfile so the image stays small (no copy of node_modules
 * with dev deps + transitive bundles).
 */
const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
