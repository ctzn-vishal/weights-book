import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { Fact } from '@/components/book/Fact';
import { FactPositioner } from '@/components/book/FactPositioner';
import { TopBar } from '@/components/book/SiteChrome';
import { SITE_URL } from '@/lib/site';
import { findTask, taskHref } from '@/lib/task-routes';
import { book, entryHref, entryLabel, splitPartTitle } from '@/lib/toc';
import cover from '@/public/cover.png';

export const metadata: Metadata = {
  title: { absolute: `${book.title}: ${book.subtitle}` },
  alternates: { canonical: SITE_URL },
};

const COVER_ALT = `Cover of ${book.title}: ${book.subtitle}, by ${book.author}. Circles of many sizes rest on a beam that balances on an amber pivot set to one side of the beam's midpoint.`;

const ROUTES = [
  { who: 'Everyone', href: '/ch00-start-here', go: 'Chapter 0', rest: 'the three decisions, one at a time' },
  { who: 'Describing a population', href: taskHref(findTask('turnout-denominator')), go: 'Chapters 1–3', rest: 'estimands, weights, and design-based uncertainty' },
  { who: 'Regression and causal questions', href: taskHref(findTask('weighted-regression')), go: 'Chapters 4–7', rest: 'explicit and hidden weights, and where to cluster' },
  { who: 'Working with one survey', href: taskHref(findTask('choose-survey')), go: 'Chapter 8', rest: 'the field guide to six surveys' },
  { who: 'Asking whether the data can answer at all', href: taskHref(findTask('nonresponse-assumption')), go: 'Chapter 9', rest: 'identification: what the file determines, and under which assumption' },
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
            <p className="cv-eyebrow">An online book</p>
            <p className="cv-lede">
              You have the public-use file open. The referee report is due, or the second-year paper is, and the questions
              that stop you are not in the econometrics sequence. Should I use the weights, and which column is the weight?
              Why does my replication of a Census number come out different? My advisor says cluster by state and the
              referee says by county; who is right, and how would I know? Is the standard error the software printed the
              standard error of anything? And can this file answer my question at all, or only under an assumption I
              have not written down?
            </p>
            <div className="cv-actions">
              <Link className="cv-cta" href="/ch00-start-here">
                Start reading: Chapter 0 <span aria-hidden="true">→</span>
              </Link>
              <Link className="cv-more" href="/tasks">
                Find an answer
              </Link>
              <a className="cv-more" href="#cv-contents">
                Browse the contents
              </a>
            </div>
            <p>
              This book answers those questions with the surveys you actually use and numbers you can check. In one
              release the Census Bureau reported that <Fact id="ch1.pov_spm_child_2021" /> of American children were poor
              and that <Fact id="ch1.pov_off_child_2021" /> were. A Medicaid-expansion regression on the American Community
              Survey has a standard error <Fact id="ch6.ratio_state_hc1" /> as large once the question is which states
              decided, not how many people were interviewed. A ranking of state uninsured rates looks definitive, and the
              survey&apos;s own replicate weights can tell apart <Fact id="ch3lab.adj_sig_sdr" /> of its 50 neighbouring
              pairs. One election file supports a Black–White turnout gap of{' '}
              <Fact id="ch1.turnout_gap_race_census_2020" /> points or <Fact id="ch1.turnout_gap_race_resp_2020" />, and
              with no assumption about the people who gave no answer, anything from <Fact id="ch9.gap_lower_2020" /> to{' '}
              <Fact id="ch9.gap_upper_2020" />. None of these is a mistake. Each is a number answering a question nobody
              wrote down: who it describes, whether the data can determine it, how each observation counts, and what could
              have come out differently.
            </p>
            <p>
              The cover shows a beam balanced on a pivot set to one side. Move the pivot and the same circles tip the other
              way. A survey weight, a regression&apos;s hidden weight, a choice of cluster: each one moves the pivot. Every
              chapter starts from a real study or a published number, works the question by hand before any software, and
              ends by saying what the analysis does not establish. The last part asks the question underneath all of them,
              for descriptions and for effects: which assumption connects this file to the quantity, and what is left when
              the assumption is removed. The examples come from political science, labor and
              health economics, and public health, because that is where the questions come from.
            </p>
            <ul className="cv-moments" aria-label="Four moments from the book">
              <li>
                <Link href="/ch01-estimands">
                  <span className="cv-moment-num">
                    <Fact id="ch1.pov_spm_child_2021" /> and <Fact id="ch1.pov_off_child_2021" />
                  </span>
                  <span className="cv-moment-txt">Two child poverty rates, one year, one survey. Chapter 1 asks what each one is a rate of.</span>
                </Link>
              </li>
              <li>
                <Link href="/ch06-clustering">
                  <span className="cv-moment-num"><Fact id="ch6.ratio_state_hc1" /></span>
                  <span className="cv-moment-txt">The standard error when thirty states, not a million records, are the units. Chapters 6 and 7 ask whose decision it was.</span>
                </Link>
              </li>
              <li>
                <Link href="/ch03-lab-replicates">
                  <span className="cv-moment-num"><Fact id="ch3lab.adj_sig_sdr" /> of 50</span>
                  <span className="cv-moment-txt">Neighbouring states a ranking can actually tell apart. Lab 3 lets the replicate weights speak.</span>
                </Link>
              </li>
              <li>
                <Link href="/ch09-identification">
                  <span className="cv-moment-num">
                    <Fact id="ch9.gap_lower_2020" /> to <Fact id="ch9.gap_upper_2020" />
                  </span>
                  <span className="cv-moment-txt">The turnout gap one file supports before anyone assumes how nonrespondents voted. Chapter 9 asks what the data can determine.</span>
                </Link>
              </li>
            </ul>
            <blockquote className="cv-mnemonic">
              <p>What is this number a weighted average of, and who chose the weights?</p>
            </blockquote>
            <p className="cv-fine">
              Written for doctoral students and applied researchers in economics, political science, sociology, psychology,
              marketing, and public health who have taken an econometrics or statistics sequence but no course in survey
              sampling. The data are public surveys: the ACS, the CPS, the American Time Use Survey, NHANES, NHIS, and BRFSS,
              with code in Python, R, and Stata.
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
