import type { ReactNode } from 'react';

interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}

export function DataTable<T>({ columns, data, onRowClick, emptyMessage = 'No data' }: DataTableProps<T>) {
  const defaultRender = (row: T, key: string): ReactNode => {
    const value = (row as Record<string, unknown>)[key];
    if (value == null) return '';
    return String(value);
  };

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50 border-b border-border">
            {columns.map((col) => (
              <th key={col.key} className={`px-4 py-3 text-left font-medium text-muted ${col.className || ''}`}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-muted">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, i) => (
              <tr
                key={i}
                onClick={() => onRowClick?.(row)}
                className={`border-b border-border last:border-0 ${onRowClick ? 'cursor-pointer hover:bg-slate-50' : ''}`}
              >
                {columns.map((col) => (
                  <td key={col.key} className={`px-4 py-3 ${col.className || ''}`}>
                    {col.render ? col.render(row) : defaultRender(row, col.key)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
