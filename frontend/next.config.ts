import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output for the Docker image (see Dockerfile).
  output: "standalone",
};

export default nextConfig;
