/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  trailingSlash: true,
  skipTrailingSlashRedirect: true,
  images: {
    unoptimized: true,
  },
  async redirects() {
    return [
      {
        source: "/ai-plugin.json",
        destination: "/.well-known/ai-plugin.json",
        permanent: true,
      },
      // Redirect agents.md to agents-md (avoids trailingSlash 308 loop on .md extension)
      {
        source: "/agents.md",
        destination: "/agents-md",
        permanent: false,
      },
      {
        source: "/AGENTS.md",
        destination: "/agents-md",
        permanent: true,
      },
    ];
  },
  // 反向代理：前端 9999 上的 /api/* 转发到后端容器（compose 内网）
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://api:9999/:path*",
      },
    ];
  },
};

export default nextConfig;
