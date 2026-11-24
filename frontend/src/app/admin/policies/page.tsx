/**
 * سیاست پاسخ‌گویی — سه حالت + پیش‌فرض سامانه + توضیح اولویت‌ها (PRD §6).
 */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookLock, Scale, Sparkles, Settings } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Button, Card, Select, Badge } from '@/components/ui';
import { useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { POLICY_LABELS } from '@/lib/constants';
import type { SystemSettings } from '@/types';

const POLICY_INFO: Record<string, { icon: typeof BookLock; title: string; description: string; example: string }> = {
  KNOWLEDGE_ONLY: {
    icon: BookLock,
    title: 'فقط پایگاه دانش',
    description: 'هوش مصنوعی فقط از اطلاعات تأییدشده مدیر پاسخ می‌دهد.',
    example: 'اگر پاسخ معتبر در پایگاه دانش نباشد، صراحتاً اعلام می‌کند اطلاعات کافی موجود نیست.',
  },
  HYBRID: {
    icon: Scale,
    title: 'ترکیبی (هوشمند)',
    description: 'ابتدا پایگاه دانش اختصاصی جستجو می‌شود؛ در صورت ناکافی بودن، دانش عمومی مدل به کمک می‌آید.',
    example: 'بهترین حالت برای اکثر سازمان‌ها — پاسخ‌های سفارشی با پوشش کامل.',
  },
  FREE_AI: {
    icon: Sparkles,
    title: 'هوش مصنوعی آزاد',
    description: 'مدل به‌صورت آزادانه و بر اساس دانش عمومی خود پاسخ می‌دهد.',
    example: 'مناسب پرسش‌های عمومی؛ محتوای اختصاصی سازمان الزاماً ملاک نیست.',
  },
};

export default function PoliciesPage() {
  const toast = useToast();
  const { isSuperAdmin } = useAuth();
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.settings.get().then(setSettings).catch((e) => toast.error(e instanceof ApiError ? e.message : 'دریافت تنظیمات ناموفق بود.'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function updatePolicy(policy: string) {
    if (!settings) return;
    setSaving(true);
    try {
      const updated = await api.settings.update({ default_response_policy: policy as SystemSettings['default_response_policy'] });
      setSettings(updated);
      toast.success('سیاست پیش‌فرض سامانه بروزرسانی شد.');
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'بروزرسانی ناموفق بود.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PageHeader title="سیاست پاسخ‌گویی" description="نحوه پاسخ‌دهی هوش مصنوعی — قابل تعیین برای کل سامانه، هر گروه و هر کاربر" />

      {/* System default */}
      <Card title="سیاست پیش‌فرض کل سامانه" description="برای کاربران و گروه‌هایی که سیاست اختصاصی ندارند اعمال می‌شود"
        actions={isSuperAdmin ? undefined : <Badge tone="warn">فقط مدیر کل</Badge>}>
        <div className="flex flex-wrap items-end gap-4">
          <Select
            label="سیاست پیش‌فرض"
            value={settings?.default_response_policy || ''}
            onChange={(e) => updatePolicy(e.target.value)}
            disabled={!isSuperAdmin || saving}
            options={Object.entries(POLICY_LABELS).map(([value, label]) => ({ value, label }))}
            className="!w-64"
          />
          <Link href="/admin/system-settings" className="mb-2 inline-flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 hover:underline">
            <Settings className="h-3.5 w-3.5" />
            سایر تنظیمات سامانه
          </Link>
        </div>
      </Card>

      {/* Three policy cards */}
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {Object.entries(POLICY_INFO).map(([key, info]) => {
          const Icon = info.icon;
          const active = settings?.default_response_policy === key;
          return (
            <div
              key={key}
              className={`rounded-2xl border p-5 shadow-sm transition ${
                active
                  ? 'border-blue-500 bg-blue-500/5 dark:bg-blue-500/10'
                  : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60'
              }`}
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="rounded-xl bg-blue-500/10 p-2.5 text-blue-600 dark:text-blue-400">
                  <Icon className="h-5 w-5" />
                </div>
                {active && <Badge tone="info">پیش‌فرض فعلی</Badge>}
              </div>
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">{info.title}</h3>
              <p className="mt-2 text-xs leading-6 text-slate-500 dark:text-slate-400">{info.description}</p>
              <p className="mt-3 rounded-xl bg-slate-50 dark:bg-slate-900/50 p-3 text-[11px] leading-5 text-slate-500 dark:text-slate-400">{info.example}</p>
            </div>
          );
        })}
      </div>

      {/* Priority explainer */}
      <Card className="mt-6" title="اولویت اعمال سیاست">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="rounded-xl bg-blue-500/10 px-4 py-2 font-bold text-blue-600 dark:text-blue-400">تنظیم اختصاصی کاربر</span>
          <span className="text-slate-400">← اولویت دارد بر →</span>
          <span className="rounded-xl bg-violet-500/10 px-4 py-2 font-bold text-violet-600 dark:text-violet-400">تنظیم گروه</span>
          <span className="text-slate-400">← اولویت دارد بر →</span>
          <span className="rounded-xl bg-slate-500/10 px-4 py-2 font-bold text-slate-600 dark:text-slate-300">تنظیمات عمومی سامانه</span>
        </div>
        <p className="mt-4 text-xs leading-6 text-slate-500 dark:text-slate-400">
          برای تعیین سیاست اختصاصی یک کاربر، از صفحه <Link href="/admin/users" className="text-blue-600 dark:text-blue-400 hover:underline">مدیریت کاربران</Link> و
          برای یک گروه، از صفحه <Link href="/admin/groups" className="text-blue-600 dark:text-blue-400 hover:underline">مدیریت گروه‌ها</Link> اقدام کنید.
        </p>
      </Card>
    </div>
  );
}