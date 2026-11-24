/**
 * لاگ درخواست‌ها — audit log با فیلتر و صفحه‌بندی سرور (PRD §16).
 */
'use client';

import { useState } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, ScrollText } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Button, Badge, Select } from '@/components/ui';
import { useApiList, useDebounce } from '@/lib/hooks';
import { fmtDateTime, fmtNum } from '@/lib/format';
import { actionTypeLabel, ACTION_TYPE_LABELS } from '@/lib/constants';
import { api, downloadFile } from '@/lib/api';
import { useToast } from '@/components/ui/overlays';
import type { AuditLogEntry } from '@/types/admin';

const PAGE_SIZE = 25;

export default function RequestLogsPage() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search);
  const [actionType, setActionType] = useState('');
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const { data, loading } = useApiList<AuditLogEntry>(
    () => api.admin.auditLogs({ search: debouncedSearch || undefined, action_type: actionType || undefined, page, page_size: PAGE_SIZE }),
    [debouncedSearch, actionType, page]
  );

  async function exportCsv() {
    setExporting(true);
    try {
      await downloadFile('/admin/export?entity=audit_logs', 'audit-logs.csv');
    } catch {
      toast.error('خروجی CSV ناموفق بود.');
    } finally {
      setExporting(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));

  return (
    <div>
      <PageHeader
        title="لاگ درخواست‌ها"
        description="تمام رخدادهای امنیتی و عملیات مدیریتی با مقادیر قبل/بعد"
        actions={
          <Button variant="outline" onClick={exportCsv} loading={exporting}>خروجی CSV</Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="جستجو در کاربر یا منبع…"
          className="w-56 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3.5 py-2 text-sm text-slate-800 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
        />
        <Select
          value={actionType}
          onChange={(e) => {
            setActionType(e.target.value);
            setPage(1);
          }}
          options={Object.entries(ACTION_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
          placeholder="همه رخدادها"
          className="!w-48"
        />
        <span className="mr-auto text-xs text-slate-400">{fmtNum(data?.total ?? 0)} رخداد</span>
      </div>

      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 shadow-sm overflow-hidden">
        {loading ? (
          <p className="py-20 text-center text-sm text-slate-400">در حال بارگذاری…</p>
        ) : (data?.items || []).length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-16 text-slate-400">
            <ScrollText className="h-8 w-8" />
            <p className="text-sm">رخدادی یافت نشد</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
            {(data?.items || []).map((log) => {
              const hasPayload = log.old_values || log.new_values;
              const isOpen = expanded === log.id;
              return (
                <div key={log.id}>
                  <button
                    className="flex w-full items-center gap-3 px-4 py-3 text-right transition hover:bg-slate-50 dark:hover:bg-slate-700/30"
                    onClick={() => setExpanded(isOpen ? null : log.id)}
                  >
                    <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={
                          log.action_type.includes('FAILED') ? 'danger' :
                          log.action_type.includes('DELETE') ? 'warn' :
                          log.action_type.includes('LOGIN') ? 'success' : 'info'
                        }>
                          {actionTypeLabel(log.action_type)}
                        </Badge>
                        <span className="text-sm text-slate-700 dark:text-slate-200">{log.target_resource}</span>
                        {log.actor_username && <span className="text-xs text-slate-400" dir="ltr">@{log.actor_username}</span>}
                      </div>
                    </div>
                    <span className="hidden shrink-0 text-xs text-slate-400 sm:block">{fmtDateTime(log.created_at)}</span>
                    {log.ip_address && <span className="hidden shrink-0 text-xs text-slate-400 lg:block" dir="ltr">{log.ip_address}</span>}
                  </button>
                  {isOpen && hasPayload && (
                    <div className="grid gap-3 bg-slate-50/60 dark:bg-slate-900/40 px-4 py-3 sm:grid-cols-2">
                      {log.old_values && (
                        <div>
                          <p className="mb-1.5 text-xs font-bold text-red-500">مقادیر قبلی</p>
                          <pre className="overflow-x-auto rounded-xl bg-slate-100 dark:bg-slate-800 p-3 text-[11px] leading-5 text-slate-600 dark:text-slate-300" dir="ltr">
                            {JSON.stringify(log.old_values, null, 2)}
                          </pre>
                        </div>
                      )}
                      {log.new_values && (
                        <div>
                          <p className="mb-1.5 text-xs font-bold text-emerald-500">مقادیر جدید</p>
                          <pre className="overflow-x-auto rounded-xl bg-slate-100 dark:bg-slate-800 p-3 text-[11px] leading-5 text-slate-600 dark:text-slate-300" dir="ltr">
                            {JSON.stringify(log.new_values, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        {(data?.total ?? 0) > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-slate-100 dark:border-slate-700/60 px-4 py-3">
            <span className="text-xs text-slate-400">صفحه {fmtNum(page)} از {fmtNum(totalPages)}</span>
            <div className="flex gap-1">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)} icon={<ChevronRight className="h-4 w-4" />}>
                قبلی
              </Button>
              <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                بعدی <ChevronLeft className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}