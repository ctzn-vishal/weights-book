import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { Source_Serif_4, Inter, JetBrains_Mono } from 'next/font/google';
import 'katex/dist/katex.min.css';
import './globals.css';

const serif = Source_Serif_4({ subsets: ['latin'], variable: '--font-source-serif', display: 'swap' });
const sans = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains', display: 'swap' });

export const metadata: Metadata = {
  title: { default: 'Weights, Design, and Estimands', template: '%s · Weights, Design, and Estimands' },
  description: 'A field guide for applied researchers on survey weights, sampling design, and estimands.',
  // Draft: excluded from indexing until the verification gate passes.
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
