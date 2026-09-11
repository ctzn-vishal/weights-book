import { formatValue } from '@/lib/format';
import type { TableFigure } from '@/lib/types';

type Cell = string | number | boolean | null | undefined;

const truthy = (v: Cell) => v === true || v === 1 || v === 'true' || v === 'yes';

/**
 * A numeric table from a figure artifact (CONTRACT §5: numeric tables are
 * never hand-typed markdown). Cells format by their column's format code;
 * numeric columns right-align unless the column says otherwise.
 *
 * `highlight_key` names a column (usually boolean, and it need not be one of
 * the displayed columns) whose truthy rows are highlighted. For convenience,
 * when no row has a truthy value there, a row whose first-column value equals
 * `highlight_key` is highlighted instead.
 */
export function TableChart({ fig }: { fig: TableFigure }) {
  const rows = fig.rows as Record<string, Cell>[];
  const hk = fig.highlight_key;
  const firstKey = fig.columns[0]?.key;
  const byFlag = hk ? rows.some((row) => truthy(row[hk])) : false;
  const isHighlighted = (row: Record<string, Cell>) =>
    !hk ? false : byFlag ? truthy(row[hk]) : firstKey !== undefined && row[firstKey] === hk;

  const numeric = (key: string) => {
    const vals = rows.map((row) => row[key]).filter((v) => v !== null && v !== undefined && v !== '');
    return vals.length > 0 && vals.every((v) => typeof v === 'number');
  };
  const cols = fig.columns.map((c) => ({ ...c, align: c.align ?? (numeric(c.key) ? 'right' : 'left') }));
  const show = (v: Cell, format: TableFigure['columns'][number]['format']) => {
    if (v === null || v === undefined || v === '') return '—';
    if (typeof v === 'number') return formatValue(v, format);
    if (typeof v === 'boolean') return v ? 'Yes' : 'No';
    return v;
  };

  return (
    <div className="tbl-wrap" tabIndex={0} role="region" aria-label={fig.title ?? fig.alt}>
      <table className="tbl">
        <caption className="sr-only">{fig.alt}</caption>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c.key} scope="col" className={`al-${c.align}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={isHighlighted(row) ? 'is-highlight' : undefined}>
              {cols.map((c, j) =>
                j === 0 ? (
                  <th key={c.key} scope="row" className={`al-${c.align}`} style={{ fontWeight: 'inherit' }}>
                    {show(row[c.key], c.format)}
                  </th>
                ) : (
                  <td key={c.key} className={`al-${c.align}`}>
                    {show(row[c.key], c.format)}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
