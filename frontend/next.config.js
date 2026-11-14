/** @type {import('next').NextConfig} */

// localhost is the default only in `next dev`. A deployed build proxies to
// NEXT_PUBLIC_API_URL when one is set, and otherwise has no proxy at all: it
// runs in demo mode (lib/demo.ts) rather than calling the visitor's machine.
const apiUrl =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '')

const nextConfig = {
  // Two dev servers in one checkout must not share a build directory: the e2e
  // suite (playwright.config.ts) and any side-by-side preview set their own.
  distDir: process.env.NEXT_DIST_DIR || '.next',
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
