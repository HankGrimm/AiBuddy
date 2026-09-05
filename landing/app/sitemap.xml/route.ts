export async function GET() {
  const base = 'https://monad-mate-landing-production.up.railway.app'
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>${base}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>${base}/llms.txt</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>
  <url><loc>${base}/llms-full.txt</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>
  <url><loc>${base}/agents.md</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>
  <url><loc>${base}/agent.md</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>
  <url><loc>${base}/agent.json</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>${base}/agent-card.json</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>${base}/mcp-server-card.json</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>${base}/agent-manifest.txt</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>${base}/sdks.txt</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>${base}/openapi.json</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>
  <url><loc>${base}/README.md</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>
  <url><loc>${base}/api.md</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
</urlset>`
  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  })
}
