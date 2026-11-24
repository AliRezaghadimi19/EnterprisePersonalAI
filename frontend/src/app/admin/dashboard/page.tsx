/**
 * داشبورد مدیریت — real stats from /admin/stats + recharts visualizations.
 */
'use client';

import { useEffect, useState } from 'react';
import { Users, UserCheck, Building2, MessagesSquare, Bot, BookOpen, Coins, HardDrive } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Card, Select } from '@/components/ui';
import { StatCard } from '@/components/ui/overlays';
import { UsageAreaChart, CategoryBarChart, DistributionPieChart } from '@/components/admin/charts';
import { api } from '@/lib/api';
import { fmtNum } from '@/lib/format';
import { POLICY_LABELS } from '@/lib/constants';
import type { DashboardStats } from '@/types/admin';

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.admin.stats(days);
        if (!cancelled) setStats(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'خطا در دریافت آمار');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [days]);

  const t = stats?.totals;

  return (
    <div>
      <PageHeader
        title="داشبورد مدیریت"
        description="نمای کلی وضعیت سامانه"
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

      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-500">
          {error}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard title="کل کاربران" value={fmtNum(t?.users)} icon={<Users className="h-5 w-5" />} loading={loading} hint={`${fmtNum(stats?.auth_types.LOCAL)} داخلی، ${fmtNum(stats?.auth_types.ACTIVE_DIRECTORY)} AD`} />
        <StatCard title="کاربران فعال" value={fmtNum(t?.active_users)} icon={<UserCheck className="h-5 w-5" />} tone="emerald" loading={loading} />
        <StatCard title="گروه‌ها" value={fmtNum(t?.groups)} icon={<Building2 className="h-5 w-5" />} tone="violet" loading={loading} />
        <StatCard title="مکالمات" value={fmtNum(t?.conversations)} icon={<MessagesSquare className="h-5 w-5" />} tone="amber" loading={loading} hint={`${fmtNum(t?.messages)} پیام`} />
        <StatCard title="مدل‌های هوش مصنوعی" value={fmtNum(t?.models)} icon={<Bot className="h-5 w-5" />} loading={loading} hint={`${fmtNum(t?.providers)} Provider`} />
        <StatCard title="اسناد پایگاه دانش" value={fmtNum(t?.documents)} icon={<BookOpen className="h-5 w-5" />} tone="emerald" loading={loading} />
        <StatCard title="مصرف توکن (ماه)" value={fmtNum(stats?.token_usage.month)} icon={<Coins className="h-5 w-5" />} tone="amber" loading={loading} hint={`${fmtNum(stats?.token_usage.questions_month)} سؤال در ماه`} />
        <StatCard title="هزینه تخمینی (ماه)" value={`$${fmtNum((stats?.token_usage.estimated_cost ?? 0).toFixed(2))}`} icon={<HardDrive className="h-5 w-5" />} tone="red" loading={loading} />
      </div>

      {/* Charts */}
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card title="روند پیام‌ها و توکن" description={`بازه ${fmtNum(days)} روز گذشته`}>
          {stats?.messages_per_day.length ? (
            <UsageAreaChart data={stats.messages_per_day} dataKey="count" label="پیام" />
          ) : (
            <p className="py-16 text-center text-xs text-slate-400">داده‌ای در این بازه موجود نیست</p>
          )}
        </Card>

        <Card title="مصرف به تفکیک مدل" description="تعداد پیام per مدل">
          {stats?.messages_per_model.length ? (
            <CategoryBarChart data={stats.messages_per_model} nameKey="model_name" valueKey="count" label="پیام" />
          ) : (
            <p className="py-16 text-center text-xs text-slate-400">داده‌ای موجود نیست</p>
          )}
        </Card>

        <Card title="توزیع سیاست پاسخ‌گویی کاربران">
          {stats?.policy_distribution.length ? (
            <DistributionPieChart
              data={stats.policy_distribution.map((p) => ({
                name: POLICY_LABELS[p.policy] || p.policy,
                value: p.count,
              }))}
              nameKey="name"
              valueKey="value"
            />
          ) : (
            <p className="py-16 text-center text-xs text-slate-400">داده‌ای موجود نیست</p>
          )}
        </Card>

        <Card title="پرتکرارترین کاربران" description="بر اساس تعداد پیام">
          {stats?.top_users.length ? (
            <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
              {stats.top_users.map((u, idx) => (
                <li key={u.user_id} className="flex items-center gap-3 py-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600/10 text-xs font-bold text-blue-600 dark:text-blue-400">
                    {fmtNum(idx + 1)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{u.full_name}</p>
                    <p className="text-xs text-slate-400">@{u.username}</p>
                  </div>
                  <span className="text-sm font-bold text-slate-700 dark:text-slate-200">{fmtNum(u.message_count)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-16 text-center text-xs text-slate-400">داده‌ای موجود نیست</p>
          )}
        </Card>
      </div>
    </div>
  );
}