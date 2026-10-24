import type { Metadata } from 'next';
import Link from 'next/link';
import { TopBar } from '@/components/book/SiteChrome';
import { absoluteUrl } from '@/lib/site';
import { taskHref, taskRoutes, type TaskGroup } from '@/lib/task-routes';
import { findEntry, entryLabel } from '@/lib/toc';

export const metadata: Metadata = {
  title: 'Find an answer',
  description: 'Find the section on survey weights, target populations, design-based uncertainty, regression, and identification that answers your research question.',
  alternates: { canonical: absoluteUrl('/tasks') },
};

const GROUPS: readonly TaskGroup[] = ['Define the quantity', 'Declare the survey', 'Estimate and report', 'Check identification'];

export default function TasksPage() {
  return (
    <>
      <TopBar />
      <main id="main" className="bk-tasks">
        <header className="bk-tasks-head">
          <p className="bk-kicker">Find a section</p>
          <h1 className="bk-title">Find an answer</h1>
          <p className="bk-dek">Start with the question you have about a file. Each link goes to a specific section of the book.</p>
          <Link href="/" className="bk-tasks-home">Browse all chapters</Link>
        </header>
        {GROUPS.map((group) => (
          <section key={group} className="bk-tasks-group" aria-labelledby={`group-${group.toLowerCase().replaceAll(' ', '-')}`}>
            <h2 id={`group-${group.toLowerCase().replaceAll(' ', '-')}`}>{group}</h2>
            <ul>
              {taskRoutes.filter((task) => task.group === group).map((task) => {
                const entry = findEntry(task.slug)?.entry;
                if (!entry) throw new Error(`Unknown chapter for task "${task.id}"`);
                return (
                  <li key={task.id}>
                    <Link className="bk-task-link" href={taskHref(task)}>
                      <span className="bk-task-question">{task.question}</span>
                      <span className="bk-task-description">{task.description}</span>
                      <span className="bk-task-location">{entryLabel(entry)} · {entry.title}</span>
                    </Link>
                    {task.related ? (
                      <Link href={taskHref(task.related)} className="bk-task-related">
                        Also: {task.related.label}
                      </Link>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
        <p className="bk-tasks-foot">New to the subject? <Link href="/ch00-start-here">Start with Chapter 0</Link>.</p>
      </main>
    </>
  );
}
