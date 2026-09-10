import type { NextConfig } from 'next';
import createMDX from '@next/mdx';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

// Served at vishalsingh.org/weights through a rewrite in the d3m-book project,
// and at <deployment>/weights directly. basePath is set from the first commit
// because it changes every URL the app emits.
const BASE_PATH = '/weights';

// One macro file shared with scripts/check-mdx.mjs, so the checker and the site
// render math identically. Encodes the notation contract (docs/CONTRACT.md).
const katexMacros = JSON.parse(readFileSync(join(process.cwd(), 'lib', 'katex-macros.json'), 'utf8'));

const nextConfig: NextConfig = {
  basePath: BASE_PATH,
  // Lets two agents build side by side without clobbering one .next directory.
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
  pageExtensions: ['ts', 'tsx', 'md', 'mdx'],
  async redirects() {
    return [
      // The bare deployment root has no page of its own; send it to the book.
      { source: '/', destination: BASE_PATH, basePath: false, permanent: false },
    ];
  },
};

const withMDX = createMDX({
  options: {
    // Plugins are named by string with JSON-only options: Turbopack serializes
    // loader options to Rust and cannot carry functions (Next 16.3 MDX guide).
    remarkPlugins: [
      ['remark-gfm', {}],
      // Single-dollar math is OFF because this book is full of currency
      // ("$74,580"). Inline math is $$...$$ within a line; display math is a
      // $$ fence on its own lines.
      ['remark-math', { singleDollarTextMath: false }],
    ],
    rehypePlugins: [
      ['rehype-slug', {}],
      ['rehype-katex', { macros: katexMacros, strict: 'ignore' }],
    ],
  },
});

export default withMDX(nextConfig);
