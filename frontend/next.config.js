/** @type {import('next').NextConfig} */

// localhost is the default only in `next dev`. A deployed build proxies to
// NEXT_PUBLIC_API_URL when one is set, and otherwise has no proxy at all: it
// runs in demo mode (lib/demo.ts) rather than calling the visitor's machine.
const apiUrl =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '')

const nextConfig = {
  // The UI tests run their own `next dev` with a fake backend address. Sharing `.next`
  // with a dev server already running let their build overwrite its chunks, so the dev
  // server then called the fake address (found 2026-11-16). They build elsewhere.
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
