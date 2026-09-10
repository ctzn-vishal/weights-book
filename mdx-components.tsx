import type { MDXComponents } from 'mdx/types';

// Replaced by the front-end agent with the full component set (docs/CONTRACT.md §8).
const components: MDXComponents = {};

export function useMDXComponents(): MDXComponents {
  return components;
}
