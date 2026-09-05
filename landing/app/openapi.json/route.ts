export async function GET() {
  const upstream = 'https://monad-mate-trust-api-production.up.railway.app/openapi.json'
  const res = await fetch(upstream, { next: { revalidate: 3600 } })
  const data = await res.json()
  return Response.json(data)
}
