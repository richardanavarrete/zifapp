import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // API routes are now local Next.js route handlers - no rewrites needed
  serverExternalPackages: ["xlsx"],
};

export default nextConfig;
