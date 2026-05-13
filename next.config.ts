import type { NextConfig } from "next";

function stripTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

const internalApiUrl = stripTrailingSlash(
  process.env.INTERNAL_API_URL || "http://127.0.0.1:8000/api/v1"
);

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${internalApiUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
