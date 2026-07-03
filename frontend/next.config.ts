import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Keep Firebase out of webpack vendor chunks on the server (prevents missing @firebase.js errors).
  serverExternalPackages: ["firebase"],
};

export default nextConfig;
