/**
 * گزارش‌های مدیریتی — نمودار روندها + خروجی CSV (PRD §17).
 */
'use client';

import { useEffect, useState } from 'react';
import { Download, TrendingUp, Users, MessagesSquare } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Button, Card, Select } from '@/components/ui';
import { StatCard } from '@/components/ui/overlays';
import { useToast } from '@/components/ui/overlays';
import { UsageAreaChart, CategoryBarChart } from '@/components/admin/charts';
import { api, downloadFile, ApiError } from '@/lib/api';
import { fmtNum } from '@/lib/format';
import type { DashboardStats, UsageReport } from '@/types/admin';

const EXPORTS = [
  { entity: 'users', label: 'کاربران' },
  { entity: 'groups', label: 'گروه‌ها' },
  { entity: 'conversations', label: 'مکالمات' },
  { entity: 'audit_logs', label: 'لاگ رخدادها' },
  { entity: 'usage', label: 'مصرف' },
];

export default function ReportsPage() {
  const toast = useToast();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [usage, setUsage] = useState<UsageReport | null>(null);
  const [days, setDays] = useState(30);
  const [exporting, setExporting] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [s, u] = await Promise.all([api.admin.stats(days), api.admin.usageReport({ group_by: 'day' })]);
        setStats(s);
        setUsage(u);
      } catch (e) {
        toast.error(e instanceof ApiError ? e.message : 'دریافت گزارش‌ها ناموفق بود.');
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  async function exportCsv(entity: string) {
    setExporting(entity);
    try {
      await downloadFile(`/admin/export?entity=${entity}`, `${entity}-report.csv`);
      toast.success('خروجی CSV دانلود شد.');
    } catch {
      toast.error('خروجی ناموفق بود.');
    } finally {
      setExporting(null);
    }
  }

  return (
    <div>
      <PageHeader
        title="گزارش‌های مدیریتی"
        description="روندهای سامانه و خروجی داده‌ها"
        actions={
          <Select
            value={String(days)}
            onChange={(e) => setDays(Number(e.target.value))}
            options={[
              { value: '7', label: '۷ روز گذشته' },
              { value: '30', label: '۳۰ روز گذشته' },
              { value: '90', label: '۹۰ روز گذشته' },
            ]}
            className="!w-40 !py-2"
          />
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard title="کل سؤالات (گزارش)" value={fmtNum(usage?.summary.total_questions)} icon={<MessagesSquare className="h-5 w-5" />} />
        <StatCard title="کل توکن‌ها" value={fmtNum(usage?.summary.total_tokens)} icon={<TrendingUp className="h-5 w-5" />} tone="emerald" />
        <StatCard title="هزینه تخمینی" value={`$${fmtNum((usage?.summary.total_cost ?? 0).toFixed(2))}`} tone="amber" />
        <StatCard title="کل کاربران" value={fmtNum(stats?.totals.users)} icon={<Users className="h-5 w-5" />} tone="violet" />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card title="روند پیام‌ها" description={`${fmtNum(days)} روز گذشته`}>
          {stats?.messages_per_day.length ? (
            <UsageAreaChart data={stats.messages_per_day} dataKey="count" label="پیام" />
          ) : (
            <p className="py-16 text-center text-xs text-slate-400">داده‌ای موجود نیست</p>
          )}
        </Card>
        <Card title="روند مصرف توکن">
          {stats?.messages_per_day.length ? (
            <UsageAreaChart data={stats.messages_per_day} dataKey="tokens" label="توکن" color={undefined} />
          ) : (
            <p className="py-16 text-center text-xs text-slate-400">داده‌ای موجود نیست</p>
          )}
        </Card>
        <Card title="مصرف به تفکیک مدل (توکن)">
          {stats?.messages_per_model.length ? (
            <CategoryBarChart data={stats.messages_per_model} nameKey="model_name" valueKey="tokens" label="توکن" />
          ) : (
            <p className="py-16 text-center text-xs text-slate-400">داده‌ای موجود نیست</p>
          )}
        </Card>
        <Card title="خروجی داده‌ها (Excel/CSV)">
          <p className="mb-3 text-xs text-slate-400">فایل‌ها با کدگذاری UTF-8 و سازگار با اکسل فارسی تولید می‌شوند.</p>
          <div className="grid grid-cols-2 gap-2">
            {EXPORTS.map((item) => (
              <Button
                key={item.entity}
                variant="outline"
                size="sm"
                icon={<Download className="h-3.5 w-3.5" />}
                loading={exporting === item.entity}
                onClick={() => exportCsv(item.entity)}
              >
                {item.label}
              </Button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}