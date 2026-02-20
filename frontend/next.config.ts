import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  // For GitHub Pages deployment - set your repo name
  basePath: process.env.NODE_ENV === "production" ? "/TrendEdge" : "",
  assetPrefix: process.env.NODE_ENV === "production" ? "/TrendEdge/" : "",
  // API URL will be set via environment variable in production
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

export default nextConfig;
