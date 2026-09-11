import type { Metadata } from 'next';
import Link from 'next/link';
import { TopBar } from '@/components/book/SiteChrome';
import { SITE_URL } from '@/lib/site';
import { book, entryHref, entryLabel, splitPartTitle } from '@/lib/toc';

export const metadata: Metadata = {
  title: { absolute: `${book.title}: ${book.subtitle}` },
  alternates: { canonical: SITE_URL },
};

const DECISIONS = [
  {
    name: 'Target',
    question: 'Who and what does the number describe?',
    text: 'The target population, the unit, and the exact quantity: a mean over person-days, a share of households, a regression coefficient, an average treatment effect. Estimand, estimator, and estimate are three different objects.',
  },
  {
    name: 'Contribution',
    question: 'How does each observation count?',
    text: 'Design weights, nonresponse and calibration adjustments, frequency and precision weights, and the implicit weights a regression places on heterogeneous effects, which nobody chose explicitly.',
  },
  {
    name: 'Uncertainty',
    question: 'What could have come out differently?',
    text: 'The repetition that makes an estimate vary: sampling, assignment, nonresponse, or a model. The sampling design and the construction of the weights both determine the variance, and the variance estimator has to match them.',
  },
];

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
        <p className="cv-eyebrow">An online booklet</p>
        <h1 className="cv-title">{book.title}</h1>
        <p className="cv-subtitle">{book.subtitle}</p>
        <p className="cv-author">{book.author}</p>

        <div className="cv-pitch">
          <p>
            Applied researchers often ask whether they should use the survey weights. The question is incomplete. A
            defensible answer separates three decisions: the population quantity the analysis targets, the way each
            observation enters the estimator, and the sampling or assignment design that governs the uncertainty.
            Econometrics, survey statistics, epidemiology, and political science each teach part of this problem, with
            different vocabularies and different defaults.
          </p>
          <p>
            This booklet connects the three decisions in one applied workflow. Each chapter starts from a question with
            two or more defensible-looking answers, such as how much Americans work or how many adults with hypertension
            have it under control, and shows which decision separates the answers. The data are public surveys applied
            researchers already use: the American Community Survey, the Current Population Survey, the American Time Use
            Survey, NHANES, NHIS, and BRFSS. One question recurs throughout.
          </p>
        </div>
        <blockquote className="cv-mnemonic">
          <p>What is this number a weighted average of, and who chose the weights?</p>
        </blockquote>

        <section className="cv-section" aria-labelledby="cv-decisions">
          <h2 className="cv-h2" id="cv-decisions">
            Three decisions
          </h2>
          <div className="cv-trio">
            {DECISIONS.map((d, i) => (
              <div key={d.name} className="cv-card">
                <p className="cv-card-n">{String.fromCharCode(65 + i)}</p>
                <h3>{d.name}</h3>
                <p className="q">{d.question}</p>
                <p>{d.text}</p>
              </div>
            ))}
          </div>
        </section>

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
    </>
  );
}
