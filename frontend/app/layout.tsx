import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Circuit OS — AI Hardware Compiler',
  description: 'Natural language to validated circuit design',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
