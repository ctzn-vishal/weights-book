'use client';

import { useMemo, useState } from 'react';
import clsx from 'clsx';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';
import { Note, WidgetFrame } from './ui';
import { fmt } from './format';

export interface RejectionRow {
  design: string;
  estimator: string;
  code: string;
  /** Rejection rate of a nominal 5% test, as a proportion. */
  reject: number;
  /** Mean standard error relative to IID. */
  ratio: number;
  verdict: string;
}

type Verdict = 'right' | 'valid' | 'wrong' | 'noisy';

/** The verdict text written by build.py, classified for colour and filtering. */
function classify(v: string): Verdict {
  if (v.startsWith('matches')) return 'right';
  if (v.startsWith('valid')) return 'valid';
  if (v.startsWith('cutoff')) return 'noisy';
  return 'wrong';
}

const VERDICT_LABEL: Record<Verdict, string> = {
  right: 'Matches the design',
  valid: 'Valid, coarser',
  wrong: 'Misses dependence',
  noisy: 'Cutoff too wide',
};
const VERDICT_CLASS: Record<Verdict, string> = {
  right: 'bg-[var(--accent-subtle)] text-[var(--accent-ink)]',
  valid: 'bg-sunken text-ink-2',
  wrong: 'bg-sunken text-[var(--negative)]',
  noisy: 'bg-sunken text-ink-2',
};

const NOMINAL = 0.05;
const helper = createColumnHelper<RejectionRow>();

function RateBar({ value, max }: { value: number; max: number }) {
  const w = Math.max(0, Math.min(1, value / max));
  const nominal = Math.max(0, Math.min(1, NOMINAL / max));
  const far = value > 0.1;
  return (
    <div className="flex items-center gap-2">
      <span className="w-12 shrink-0 text-right tabular-nums">{fmt(value, 'pct1')}</span>
      <span className="relative block h-2.5 w-full min-w-16 max-w-40 overflow-hidden rounded-sm bg-sunken" aria-hidden="true">
        <span
          className={clsx('absolute inset-y-0 left-0 rounded-sm', far ? 'bg-[var(--negative)]' : 'bg-[var(--role-highlight)]')}
          style={{ width: `${w * 100}%`, opacity: far ? 0.75 : 1 }}
        />
        <span className="absolute inset-y-0 w-px bg-[var(--text)]" style={{ left: `${nominal * 100}%` }} />
      </span>
    </div>
  );
}

export function RejectionGridClient({
  rows,
  title,
  subtitle,
  note,
  source,
  alt,
}: {
  rows: RejectionRow[];
  title: string;
  subtitle?: string;
  note?: string;
  source?: string;
  alt: string;
}) {
  const designs = useMemo(() => Array.from(new Set(rows.map((r) => r.design))), [rows]);
  const [design, setDesign] = useState<string>('all');
  const [verdicts, setVerdicts] = useState<Set<Verdict>>(new Set(['right', 'valid', 'wrong', 'noisy']));
  const [sorting, setSorting] = useState<SortingState>([]);
  const max = useMemo(() => Math.max(0.2, ...rows.map((r) => r.reject)), [rows]);

  const columns = useMemo(
    () => [
      helper.accessor('design', { header: 'Design', cell: (c) => <span className="text-ink-2">{c.getValue()}</span> }),
      helper.accessor('estimator', { header: 'Estimator', cell: (c) => <span className="font-medium text-ink">{c.getValue()}</span> }),
      helper.accessor('code', {
        header: 'fixest',
        enableSorting: false,
        cell: (c) => <code className="rounded bg-sunken px-1 py-0.5 font-mono text-[0.75rem] text-ink">{c.getValue()}</code>,
      }),
      helper.accessor('reject', {
        header: () => (
          <span>
            Rejects true null <span className="font-normal text-ink-2">(nominal 5%)</span>
          </span>
        ),
        cell: (c) => <RateBar value={c.getValue()} max={max} />,
        sortDescFirst: true,
      }),
      helper.accessor('ratio', {
        header: 'SE × IID',
        cell: (c) => <span className="tabular-nums">{fmt(c.getValue(), 'ratio2')}</span>,
        sortDescFirst: true,
      }),
      helper.accessor((r) => classify(r.verdict), {
        id: 'verdict',
        header: 'Verdict',
        cell: (c) => {
          const v = c.getValue();
          return <span className={clsx('whitespace-nowrap rounded-full px-2 py-0.5 text-[0.7rem] font-medium', VERDICT_CLASS[v])}>{VERDICT_LABEL[v]}</span>;
        },
        sortingFn: (a, b) => {
          const order: Verdict[] = ['right', 'valid', 'noisy', 'wrong'];
          return order.indexOf(a.getValue('verdict')) - order.indexOf(b.getValue('verdict'));
        },
      }),
    ],
    [max],
  );

  const data = useMemo(
    () => rows.filter((r) => (design === 'all' || r.design === design) && verdicts.has(classify(r.verdict))),
    [rows, design, verdicts],
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const toggleVerdict = (v: Verdict) =>
    setVerdicts((prev) => {
      const next = new Set(prev);
      if (next.has(v)) next.delete(v);
      else next.add(v);
      return next.size ? next : prev;
    });

  return (
    <WidgetFrame title={title} subtitle={subtitle}>
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <label className="flex flex-col gap-1 text-xs font-medium text-ink-2">
          Design
          <select
            value={design}
            onChange={(e) => setDesign(e.target.value)}
            className="rounded-md border border-[var(--border-strong)] bg-surface px-2 py-1.5 text-sm font-normal text-ink"
          >
            <option value="all">All designs</option>
            {designs.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="min-w-0">
          <legend className="mb-1 text-xs font-medium text-ink-2">Verdict</legend>
          <div className="flex flex-wrap gap-1.5">
            {(Object.keys(VERDICT_LABEL) as Verdict[]).map((v) => {
              const on = verdicts.has(v);
              return (
                <button
                  key={v}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleVerdict(v)}
                  className={clsx(
                    'rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors',
                    on ? 'border-[var(--text)] bg-[var(--text)] text-[var(--surface)]' : 'border-[var(--border-strong)] bg-surface text-ink-2 hover:bg-sunken',
                  )}
                >
                  {VERDICT_LABEL[v]}
                </button>
              );
            })}
          </div>
        </fieldset>
        <div className="ml-auto text-xs text-muted tabular-nums">
          {data.length} of {rows.length} rows
        </div>
      </div>

      <div className="mt-3 overflow-x-auto [contain:inline-size]" tabIndex={0} role="region" aria-label={alt}>
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">{alt}</caption>
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-[var(--border-strong)]">
                {hg.headers.map((h) => {
                  const canSort = h.column.getCanSort();
                  const dir = h.column.getIsSorted();
                  return (
                    <th
                      key={h.id}
                      scope="col"
                      aria-sort={dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : 'none'}
                      className="whitespace-nowrap px-2 py-2 text-left align-bottom text-xs font-semibold text-ink"
                    >
                      {canSort ? (
                        <button
                          type="button"
                          onClick={h.column.getToggleSortingHandler()}
                          className="inline-flex items-center gap-1 rounded hover:text-[var(--accent-ink)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
                        >
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          <span aria-hidden="true" className={clsx('text-[0.65rem]', dir ? 'text-[var(--accent-ink)]' : 'text-muted')}>
                            {dir === 'asc' ? '▲' : dir === 'desc' ? '▼' : '⇅'}
                          </span>
                        </button>
                      ) : (
                        flexRender(h.column.columnDef.header, h.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => {
              const v = classify(row.original.verdict);
              return (
                <tr key={row.id} className={clsx('border-b border-rule align-middle', v === 'right' && 'bg-[var(--accent-subtle)]/40')}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-2 py-1.5">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-muted">
        Bars show the share of simulated data sets in which a nominal 5% test rejected a true null; the tick marks 5%. Click a
        column heading to sort.
      </p>
      {note ? <Note>{note}</Note> : null}
      {source ? <p className="mt-1 text-xs text-muted">Source: {source}</p> : null}
    </WidgetFrame>
  );
}
