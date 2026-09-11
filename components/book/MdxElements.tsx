import { isValidElement, type ComponentPropsWithoutRef } from 'react';
import Link from 'next/link';
import { withBasePath } from '@/lib/site';

/**
 * Markdown element mappings (mdx-components.tsx).
 *
 * Links: root-relative hrefs ("/ch03-design#domains") go through next/link,
 * which adds the base path and prefetches; external links stay plain anchors.
 */
export function MdxLink({ href = '', children, ...rest }: ComponentPropsWithoutRef<'a'>) {
  if (href.startsWith('/') && !href.startsWith('//')) {
    return (
      <Link href={href} {...rest}>
        {children}
      </Link>
    );
  }
  if (/^(https?:)?\/\//.test(href)) {
    return (
      <a href={href} rel="noopener noreferrer" {...rest}>
        {children}
      </a>
    );
  }
  return (
    <a href={href} {...rest}>
      {children}
    </a>
  );
}

/** h2/h3 with a hover permalink; ids come from rehype-slug. */
function anchored(Tag: 'h2' | 'h3') {
  function Heading({ id, children, ...rest }: ComponentPropsWithoutRef<'h2'>) {
    return (
      <Tag id={id} {...rest}>
        {children}
        {id ? <a className="bk-anchor" href={`#${id}`} aria-label="Link to this section" /> : null}
      </Tag>
    );
  }
  Heading.displayName = `Mdx${Tag.toUpperCase()}`;
  return Heading;
}
export const MdxH2 = anchored('h2');
export const MdxH3 = anchored('h3');

/** Plain <img> with the base path added to root-relative sources (public/ files). */
export function MdxImage({ src, alt, ...rest }: ComponentPropsWithoutRef<'img'>) {
  const resolved = typeof src === 'string' ? withBasePath(src) : src;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={resolved} alt={alt ?? ''} loading="lazy" decoding="async" {...rest} />;
}

/** Markdown tables (text only, by contract) scroll inside their own box on narrow screens. */
export function MdxTable(props: ComponentPropsWithoutRef<'table'>) {
  return (
    <div className="bk-table-scroll">
      <table {...props} />
    </div>
  );
}

/** Fenced code, highlighted at build time by rehype-pretty-code, with the language as a small label. */
export function MdxPre({ children, ...rest }: ComponentPropsWithoutRef<'pre'> & { 'data-language'?: string }) {
  let lang: string | null = rest['data-language'] ?? null;
  if (!lang && isValidElement<{ className?: string; 'data-language'?: string }>(children)) {
    const m = /language-([\w+-]+)/.exec(children.props.className ?? '');
    lang = m ? m[1] : (children.props['data-language'] ?? null);
  }
  if (lang === 'text') lang = null;
  return (
    <div className="bk-code">
      {lang ? <span className="bk-code-lang">{lang}</span> : null}
      <pre {...rest}>{children}</pre>
    </div>
  );
}
