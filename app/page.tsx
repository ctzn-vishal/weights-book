import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { Fact } from '@/components/book/Fact';
import { FactPositioner } from '@/components/book/FactPositioner';
import { TopBar } from '@/components/book/SiteChrome';
import { SITE_URL } from '@/lib/site';
import { book, entryHref, entryLabel, splitPartTitle } from '@/lib/toc';
import cover from '@/public/cover.png';

export const metadata: Metadata = {
  title: { absolute: `${book.title}: ${book.subtitle}` },
  alternates: { canonical: SITE_URL },
};

const COVER_ALT = `Cover of ${book.title}: ${book.subtitle}, by ${book.author}. Circles of many sizes rest on a beam that balances on an amber pivot set to one side of the beam's midpoint.`;

const ROUTES = [
  { who: 'Everyone', href: '/ch00-start-here', go: 'Chapter 0', rest: 'the three decisions, one at a time' },
  { who: 'Describing a population', href: '/ch01-estimands', go: 'Chapters 1–3', rest: 'estimands, weights, and design-based uncertainty' },
  { who: 'Regression and causal questions', href: '/ch04-regression', go: 'Chapters 4–6', rest: 'explicit and hidden weights, and clustering' },
  { who: 'Working with one survey', href: '/ch07-field-guide', go: 'Chapter 7', rest: 'the field guide to six surveys' },
];

export default function Home() {
  return (
    <>
      <TopBar />
      <main id="main" className="cv">
        {/* The cover image carries the visible title; this heading names the page for screen readers and search. */}
        <h1 className="sr-only">
          {book.title}: {book.subtitle}
        </h1>

        <div className="cv-hero">
          <div className="cv-cover">
            <Image
              src={cover}
              alt={COVER_ALT}
              placeholder="blur"
              loading="eager"
              fetchPriority="high"
              sizes="(min-width: 56rem) 27rem, min(90vw, 26rem)"
              className="cv-cover-img"
            />
          </div>

          <div className="cv-hero-text">
            <p className="cv-eyebrow">An online booklet</p>
            <p className="cv-lede">
              In the November 2020 Current Population Survey, <Fact id="ch1.turnout_census_2020" /> of citizen adults
              reported voting under the Census Bureau&apos;s convention. Count only the people who answered the voting
              question and the figure becomes <Fact id="ch1.turnout_resp_2020" />; drop the survey weights from that and it
              moves only to <Fact id="ch1.turnout_unw_2020" />.
            </p>
            <p>
              The gap is about who stays in the denominator, not about the weights, and neither figure reveals how the
              people who did not answer actually voted. Before asking which estimate is right, an analyst has to say what it
              describes, how each observation counts toward it, and what could have come out differently.
            </p>
            <blockquote className="cv-mnemonic">
              <p>What is this number a weighted average of, and who chose the weights?</p>
            </blockquote>
            <div className="cv-actions">
              <Link className="cv-cta" href="/ch00-start-here">
                Start reading: Chapter 0 <span aria-hidden="true">→</span>
              </Link>
              <a className="cv-more" href="#cv-contents">
                Browse the contents
              </a>
            </div>
            <p className="cv-fine">
              For doctoral students and applied researchers who have taken an econometrics sequence but no course in survey
              sampling. The data are public surveys: the ACS, the CPS, the American Time Use Survey, NHANES, NHIS, and BRFSS.
            </p>
          </div>
        </div>

        <section className="cv-section" aria-labelledby="cv-routes">
          <h2 className="cv-h2" id="cv-routes">
            Where to start
          </h2>
          <div className="cv-routes">
            {ROUTES.map((r) => (
              <Link key={r.who} className="cv-route" href={r.href}>
                <span className="who">{r.who}</span>
                <span className="go">
                  <b>{r.go}</b>: {r.rest}
                </span>
              </Link>
            ))}
          </div>
        </section>

        <section className="cv-section" aria-labelledby="cv-contents">
          <h2 className="cv-h2" id="cv-contents">
            Contents
          </h2>
          {book.parts.map((part) => {
            const { label, name } = splitPartTitle(part.title);
            return (
              <div key={part.title} className="cv-part">
                <h3 className="cv-part-title">
                  {label ?? name}
                  {label ? <span className="name">{name}</span> : null}
                </h3>
                <div className="cv-grid">
                  {part.entries.map((e) => (
                    <Link key={e.slug} className="cv-ch" href={entryHref(e)}>
                      <span className="cv-ch-num">{entryLabel(e)}</span>
                      <span className="cv-ch-title">{e.title}</span>
                      <span className="cv-ch-dek">{e.dek}</span>
                      {e.credential ? <span className="cv-ch-cred">{e.credential}</span> : null}
                    </Link>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      </main>
      <FactPositioner />
    </>
  );
}
