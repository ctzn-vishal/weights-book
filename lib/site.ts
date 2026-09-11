/**
 * Site-wide constants. BASE_PATH must equal `basePath` in next.config.ts;
 * scripts/verify-book.mjs fails the build if the two drift apart.
 */
export const BASE_PATH = '/weights';

/** Public origin the book is served from (through a rewrite on vishalsingh.org). */
export const SITE_ORIGIN = 'https://vishalsingh.org';
export const SITE_URL = `${SITE_ORIGIN}${BASE_PATH}`;

export const REPO_URL = 'https://github.com/ctzn-vishal/weights-book';

/** localStorage key for the reader's theme choice: 'light' | 'dark' | 'system'. */
export const THEME_STORAGE_KEY = 'wde-theme';

/**
 * Prefix a root-relative path with the base path. next/link and next/image add
 * the base path themselves; plain <img>, <a>, and absolute URLs need this.
 */
export function withBasePath(path: string): string {
  if (!path.startsWith('/') || path.startsWith('//')) return path;
  if (path === BASE_PATH || path.startsWith(`${BASE_PATH}/`)) return path;
  return `${BASE_PATH}${path}`;
}

/** Absolute public URL for a root-relative path, for Open Graph and canonical links. */
export function absoluteUrl(path = '/'): string {
  return `${SITE_ORIGIN}${withBasePath(path === '/' ? '' : path) || BASE_PATH}`;
}
