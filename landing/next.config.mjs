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
};

export default nextConfig;
