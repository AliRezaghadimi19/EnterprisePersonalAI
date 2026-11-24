/**
 * گزارش مصرف API — بازه زمانی + تفکیک روز/کاربر/مدل (PRD §18).
 */
'use client';

import { useCallback, useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Button, Card, Input, Select } from '@/components/ui';
import { StatCard } from '@/components/ui/overlays';
import { useToast } from '@/components/ui/overlays';
import { UsageAreaChart, CategoryBarChart } from '@/components/admin/charts';
import { api, downloadFile, ApiError } from '@/lib/api';
import { fmtNum } from '@/lib/format';
import type { UsageReport, UsageReportRow } from '@/types/admin';

export default function ApiUsagePage() {
  const toast = useToast();
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [groupBy, setGroupBy] = useState<'day' | 'user' | 'model'>('day');
  const [report, setReport] = useState<UsageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.admin.usageReport({ from_date: fromDate || undefined, to_date: toDate || undefined, group_by: groupBy });
      setReport(data);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'دریافت گزارش ناموفق بود.');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromDate, toDate, groupBy]);

  useEffect(() => {
    void fetchReport();
  }, [fetchReport]);

  async function exportCsv() {
    setExporting(true);
    try {
      await downloadFile('/admin/export?entity=usage', 'api-usage.csv');
      toast.success('خروجی دانلود شد.');
    } catch {
      toast.error('خروجی ناموفق بود.');
    } finally {
      setExporting(false);
    }
  }

  const chartData = (report?.rows || []).map((r: UsageReportRow) => ({
    date: groupBy === 'day' ? String(r.bucket) : String(r.label ?? r.bucket),
    count: r.question_count,
    tokens: r.total_tokens,
  }));

  return (
    <div>
      <PageHeader
        title="گزارش مصرف API"
        description="سؤالات، توکن‌ها و هزینه به تفکیک روز، کاربر یا مدل"
        actions={
          <Button variant="outline" icon={<Download className="h-4 w-4" />} onClick={exportCsv} loading={exporting}>خروجی CSV</Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Input label="از تاریخ" type="date" dir="ltr" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="!w-44" />
        <Input label="تا تاریخ" type="date" dir="ltr" value={toDate} onChange={(e) => setToDate(e.target.value)} className="!w-44" />
        <Select
          label="تفکیک بر اساس"
          value={groupBy}
          onChange={(e) => setGroupBy(e.target.value as 'day' | 'user' | 'model')}
          options={[
            { value: 'day', label: 'روز' },
            { value: 'user', label: 'کاربر' },
            { value: 'model', label: 'مدل' },
          ]}
          className="!w-40"
        />
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard title="کل سؤالات" value={fmtNum(report?.summary.total_questions)} loading={loading} />
        <StatCard title="کل توکن‌ها" value={fmtNum(report?.summary.total_tokens)} tone="emerald" loading={loading} />
        <StatCard title="هزینه تخمینی" value={`$${fmtNum((report?.summary.total_cost ?? 0).toFixed(4))}`} tone="amber" loading={loading} />
        <StatCard title="کاربران فعال" value={fmtNum(report?.summary.active_users)} tone="violet" loading={loading} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card title={groupBy === 'day' ? 'روند سؤالات' : 'سؤالات به تفکیک ' + (groupBy === 'user' ? 'کاربر' : 'مدل')}>
          {chartData.length ? (
            groupBy === 'day'
              ? <UsageAreaChart data={chartData} dataKey="count" label="سؤال" />
              : <CategoryBarChart data={chartData} nameKey="date" valueKey="count" label="سؤال" />
          ) : (
            <p className="py-16 text-center text-xs text-slate-400">داده‌ای در این بازه موجود نیست</p>
          )}
        </Card>
        <Card title={groupBy === 'day' ? 'روند توکن' : 'توکن به تفکیک ' + (groupBy === 'user' ? 'کاربر' : 'مدل')}>
          {chartData.length ? (
            groupBy === 'day'
              ? <UsageAreaChart data={chartData} dataKey="tokens" label="توکن" />
              : <CategoryBarChart data={chartData} nameKey="date" valueKey="tokens" label="توکن" />
          ) : (
            <p className="py-16 text-center text-xs text-slate-400">داده‌ای در این بازه موجود نیست</p>
          )}
        </Card>
      </div>

      {/* Detail table */}
      {report?.rows.length ? (
        <Card className="mt-6" title="جزئیات ردیف‌ها">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-700 text-xs text-slate-400">
                  <th className="px-3 py-2">{groupBy === 'day' ? 'تاریخ' : groupBy === 'user' ? 'کاربر' : 'مدل'}</th>
                  <th className="px-3 py-2">سؤال</th>
                  <th className="px-3 py-2">توکن</th>
                  <th className="px-3 py-2">هزینه</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700/50">
                {report.rows.slice(0, 20).map((r, idx) => (
                  <tr key={idx}>
                    <td className="px-3 py-2.5 text-slate-700 dark:text-slate-200" dir={groupBy === 'day' ? 'ltr' : undefined}>{r.label || r.bucket}</td>
                    <td className="px-3 py-2.5">{fmtNum(r.question_count)}</td>
                    <td className="px-3 py-2.5 text-slate-500 dark:text-slate-400">{fmtNum(r.total_tokens)}</td>
                    <td className="px-3 py-2.5 text-slate-500 dark:text-slate-400" dir="ltr">${r.estimated_cost.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
}