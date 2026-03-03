import type { Metadata, Viewport } from 'next'
import { Syne, DM_Mono, Plus_Jakarta_Sans } from 'next/font/google'
import './globals.css'
import Script from 'next/script'

const syne = Syne({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['600', '700', '800'],
})

const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-body',
  weight: ['400', '500', '600'],
})

const mono = DM_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500'],
})

export const metadata: Metadata = {
  title: 'Declutter — AI File Organizer',
  description: 'Find duplicates, free up space, and organize your digital life with AI.',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'Declutter',
  },
  openGraph: {
    title: 'Declutter — AI File Organizer',
    description: 'Find and remove duplicate files, blurry photos, and screenshots. Free up space in minutes.',
    type: 'website',
  },
}

export const viewport: Viewport = {
  themeColor: '#4f7cff',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${syne.variable} ${jakarta.variable} ${mono.variable}`}>
      <head>
        <link rel="icon" href="/favicon.ico" />
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body className="bg-surface text-ink font-sans antialiased">
        {children}
        {/* Service Worker registration for PWA */}
        <Script id="sw-register" strategy="afterInteractive">
          {`
            if ('serviceWorker' in navigator) {
              window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                  .then(reg => console.log('[SW] registered:', reg.scope))
                  .catch(err => console.log('[SW] error:', err));
              });
            }
          `}
        </Script>
      </body>
    </html>
  )
}
