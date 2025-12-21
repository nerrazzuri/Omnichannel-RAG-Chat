/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  eslint: {
    // Avoid failing production builds on ESLint issues
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Avoid failing production builds on TS type errors
    ignoreBuildErrors: true,
  },
  async rewrites() {
    const gwOrigin = process.env.NEXT_GATEWAY_ORIGIN || "http://localhost:3001";
    const base = gwOrigin.endsWith("/") ? gwOrigin.slice(0, -1) : gwOrigin;
    return [
      {
        source: "/api/:path*",
        destination: `${base}/api/:path*`, // Gateway service
      },
    ];
  },
};

module.exports = nextConfig;
