/**
 * DataTable — the one table used by every admin list page.
 * Client-paged mode (default) or server-paged mode via page/total/onPageChange.
 */
'use client';

import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { cn, Spinner } from '@/components/ui';
import { EmptyState } from '@/components/ui/overlays';
import { toPersianDigits } from '@/lib/jalali';

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  loading?: boolean;
  rowKey: (row: T) => string;
  rowActions?: (row: T) => ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  /** server-paged mode */
  page?: number;
  pageSize?: number;
  total?: number;
  onPageChange?: (page: number) => void;
  /** client-side filter within rows (search box shown when provided) */
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  filters?: ReactNode;
  toolbarActions?: ReactNode;
}

export function DataTable<T>({
  columns, rows, loading, rowKey, rowActions,
  emptyTitle = 'موردی یافت نشد', emptyDescription, emptyAction,
  page, pageSize = 25, total, onPageChange,
  searchValue, onSearchChange, searchPlaceholder = 'جستجو…',
  filters, toolbarActions,
}: DataTableProps<T>) {
  const [clientPage, setClientPage] = useState(1);
  const isServerPaged = typeof page === 'number' && typeof total === 'number' && !!onPageChange;
  const currentPage = isServerPaged ? (page as number) : clientPage;
  const effectiveTotal = isServerPaged ? (total as number) : rows.length;

  const pageCount = Math.max(1, Math.ceil(effectiveTotal / pageSize));

  useEffect(() => {
    if (!isServerPaged && clientPage > pageCount) setClientPage(1);
  }, [clientPage, pageCount, isServerPaged]);

  const visibleRows = useMemo(() => {
    if (isServerPaged) return rows;
    const start = (currentPage - 1) * pageSize;
    return rows.slice(start, start + pageSize);
  }, [rows, currentPage, pageSize, isServerPaged]);

  const hasToolbar = searchValue !== undefined || filters || toolbarActions;

  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 shadow-sm overflow-hidden">
      {hasToolbar && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-700/60">
          <div className="flex flex-wrap items-center gap-2">
            {searchValue !== undefined && onSearchChange && (
              <div className="relative">
                <Search className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  value={searchValue}
                  onChange={(e) => onSearchChange(e.target.value)}
                  placeholder={searchPlaceholder}
                  className="w-56 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 py-2 pr-9 pl-3 text-sm text-slate-800 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                />
              </div>
            )}
            {filters}
          </div>
          {toolbarActions && <div className="flex items-center gap-2">{toolbarActions}</div>}
        </div>
      )}

      <div className="overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Spinner className="h-7 w-7 text-blue-500" />
          </div>
        ) : visibleRows.length === 0 ? (
          <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
        ) : (
          <table className="w-full text-right text-sm">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-700 bg-slate-50/60 dark:bg-slate-900/40">
                {columns.map((col) => (
                  <th key={col.key} className={cn('px-4 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 whitespace-nowrap', col.className)}>
                    {col.header}
                  </th>
                ))}
                {rowActions && <th className="px-4 py-3 text-xs font-bold text-slate-500 dark:text-slate-400">عملیات</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700/50">
              {visibleRows.map((row) => (
                <tr key={rowKey(row)} className="transition-colors hover:bg-slate-50/60 dark:hover:bg-slate-700/30">
                  {columns.map((col) => (
                    <td key={col.key} className={cn('px-4 py-3 text-slate-700 dark:text-slate-200', col.className)}>
                      {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '—')}
                    </td>
                  ))}
                  {rowActions && <td className="px-4 py-3">{rowActions(row)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-between gap-3 border-t border-slate-100 dark:border-slate-700/60 px-4 py-3">
          <p className="text-xs text-slate-400">
            {toPersianDigits(effectiveTotal)} مورد
          </p>
          <div className="flex items-center gap-1">
            <button
              disabled={currentPage <= 1}
              onClick={() => (isServerPaged ? (onPageChange as (p: number) => void)(currentPage - 1) : setClientPage(currentPage - 1))}
              className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="صفحه قبل"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            <span className="px-3 text-xs text-slate-600 dark:text-slate-300">
              صفحه {toPersianDigits(currentPage)} از {toPersianDigits(pageCount)}
            </span>
            <button
              disabled={currentPage >= pageCount}
              onClick={() => (isServerPaged ? (onPageChange as (p: number) => void)(currentPage + 1) : setClientPage(currentPage + 1))}
              className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="صفحه بعد"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}