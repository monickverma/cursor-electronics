import type { Metadata, Viewport } from 'next'
import { Archivo, JetBrains_Mono } from 'next/font/google'
import './globals.css'

// One sans family with a width axis (lettering is set at font-stretch 88%), one mono family.
const archivo = Archivo({
  subsets: ['latin'],
  axes: ['wdth'],
  display: 'swap',
  variable: '--font-archivo',
})

const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  display: 'swap',
  variable: '--font-jetbrains',
})

export const metadata: Metadata = {
  title: 'Circuit OS — AI hardware compiler',
  description:
    'An AI hardware compiler. Plain English in; schematic, firmware, SPICE simulation, BOM and graded validation claims out. ' +
    'The model writes JSON against an IR schema; deterministic compilers produce everything downstream.',
  applicationName: 'Circuit OS',
}

export const viewport: Viewport = {
  themeColor: '#0a0a0a',
  colorScheme: 'dark',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${archivo.variable} ${jetbrains.variable}`}>
      <body>{children}</body>
    </html>
  )
}
