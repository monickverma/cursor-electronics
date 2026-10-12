/** @type {import('next').NextConfig} */

// localhost is the default only in `next dev`. A deployed build proxies to
// NEXT_PUBLIC_API_URL when one is set, and otherwise has no proxy at all: it
// runs in demo mode (lib/demo.ts) rather than calling the visitor's machine.
const apiUrl =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '')

const nextConfig = {
  async rewrites() {
    if (!apiUrl) return []
    return [
      {
        source: '/api/backend/:path*',
        destination: `${apiUrl}/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
