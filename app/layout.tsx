import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { Inter, JetBrains_Mono, Source_Serif_4 } from 'next/font/google';
import 'katex/dist/katex.min.css';
import './globals.css';
import { DraftBanner, SiteFooter } from '@/components/book/SiteChrome';
import { ThemeScript } from '@/components/book/ThemeScript';
import { SITE_ORIGIN, SITE_URL } from '@/lib/site';
import { book } from '@/lib/toc';

const serif = Source_Serif_4({
  subsets: ['latin'],
  style: ['normal', 'italic'],
  variable: '--font-source-serif',
  display: 'swap',
});
const sans = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains', display: 'swap' });

const description =
  'A field guide for applied researchers on survey weights, sampling design, and estimands: what a weighted number describes, how each observation counts, and what could have come out differently.';

export const metadata: Metadata = {
  metadataBase: new URL(SITE_ORIGIN),
  title: { default: book.title, template: `%s · ${book.title}` },
  description,
  authors: [{ name: book.author }],
  openGraph: {
    type: 'website',
    siteName: book.title,
    title: `${book.title}: ${book.subtitle}`,
    description,
    url: SITE_URL,
    locale: 'en_US',
  },
  // The share image itself is app/opengraph-image.png (Next's file convention), the cover on a wide card.
  twitter: { card: 'summary_large_image' },
  // Draft: excluded from indexing until the verification gate passes.
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body>
        <a href="#main" className="bk-skip">
          Skip to content
        </a>
        <DraftBanner />
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}
