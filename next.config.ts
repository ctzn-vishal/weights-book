import type { NextConfig } from 'next';
import createMDX from '@next/mdx';
// One macro file shared with scripts/check-mdx.mjs, so the checker and the site
// render math identically. Encodes the notation contract (docs/CONTRACT.md).
// Next evaluates the compiled config relative to the working directory, so run
// `next` from the repo root (the npm scripts and Vercel both do).
import katexMacros from './lib/katex-macros.json';

// Served at vishalsingh.org/weights through a rewrite in the d3m-book project,
// and at <deployment>/weights directly. basePath is set from the first commit
// because it changes every URL the app emits.
const BASE_PATH = '/weights';

const nextConfig: NextConfig = {
  basePath: BASE_PATH,
  // Next 16's dev server otherwise writes AGENTS.md / CLAUDE.md into the repo root.
  agentRules: false,
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
      // Build-time syntax highlighting. Both themes are emitted as CSS variables on
      // every token (--shiki-light / --shiki-dark); app/globals.css picks one by the
      // html.dark class, so the page's own theme toggle drives the code colours.
      ['rehype-pretty-code', { theme: { light: 'github-light', dark: 'github-dark-dimmed' }, keepBackground: false, defaultLang: 'text' }],
    ],
  },
});

export default withMDX(nextConfig);
