/**
 * مدیریت هوش مصنوعی — hub overview with links to providers/models/policies.
 */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Bot, Plug, Scale } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Card } from '@/components/ui';
import { api } from '@/lib/api';
import { fmtNum } from '@/lib/format';
import { POLICY_LABELS } from '@/lib/constants';
import type { AdminProvider, AdminModel } from '@/types/entities';
import type { SystemSettings } from '@/types';

export default function AIPage() {
  const [providers, setProviders] = useState<AdminProvider[]>([]);
  const [models, setModels] = useState<AdminModel[]>([]);
  const [settings, setSettings] = useState<SystemSettings | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [p, m, s] = await Promise.all([api.providers.list(), api.models.list(), api.settings.get()]);
        setProviders(p.items);
        setModels(m.items);
        setSettings(s);
      } catch { /* non-blocking */ }
    })();
  }, []);

  const activeProviders = providers.filter((p) => p.is_active).length;
  const activeModels = models.filter((m) => m.is_active).length;
  const defaultModel = models.find((m) => m.is_default);

  const hubs = [
    {
      href: '/admin/providers',
      icon: <Plug className="h-6 w-6" />,
      title: 'مدیریت Providerها',
      description: 'اتصال به سرویس‌دهندگان هوش مصنوعی (OpenAI، Anthropic، Gemini و…)، ثبت کلید API و تست اتصال',
      stat: `${fmtNum(activeProviders)} فعال از ${fmtNum(providers.length)}`,
    },
    {
      href: '/admin/models',
      icon: <Bot className="h-6 w-6" />,
      title: 'مدیریت مدل‌ها',
      description: 'افزودن مدل، تعیین مدل پیش‌فرض و جایگزین، هزینه توکن و ماتریس دسترسی گروه‌ها',
      stat: `${fmtNum(activeModels)} فعال از ${fmtNum(models.length)}`,
    },
    {
      href: '/admin/policies',
      icon: <Scale className="h-6 w-6" />,
      title: 'سیاست پاسخ‌گویی',
      description: 'تعیین نحوه پاسخ‌دهی هوش مصنوعی: فقط پایگاه دانش، ترکیبی یا آزاد — در سه سطح سامانه/گروه/کاربر',
      stat: `پیش‌فرض سامانه: ${POLICY_LABELS[settings?.default_response_policy || ''] || '—'}`,
    },
  ];

  return (
    <div>
      <PageHeader title="مدیریت هوش مصنوعی" description="مرکز کنترل Gateway، سرویس‌دهندگان و مدل‌ها" />

      <Card className="mb-6">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3 text-sm">
          <div>
            <p className="text-xs text-slate-400">مدل پیش‌فرض سامانه</p>
            <p className="mt-0.5 font-bold text-slate-700 dark:text-slate-200">{defaultModel?.display_name_fa || 'تعیین نشده'}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">سیاست پاسخ‌گویی پیش‌فرض</p>
            <p className="mt-0.5 font-bold text-slate-700 dark:text-slate-200">{POLICY_LABELS[settings?.default_response_policy || ''] || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">زبان پاسخ هوش مصنوعی</p>
            <p className="mt-0.5 font-bold text-slate-700 dark:text-slate-200">{settings?.default_ai_language === 'fa' ? 'فارسی' : settings?.default_ai_language === 'en' ? 'انگلیسی' : '—'}</p>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        {hubs.map((hub) => (
          <Link
            key={hub.href}
            href={hub.href}
            className="group rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 p-5 shadow-sm transition hover:border-blue-400 dark:hover:border-blue-500 hover:shadow-md"
          >
            <div className="mb-3 flex items-center justify-between">
              <div className="rounded-xl bg-blue-500/10 p-2.5 text-blue-600 dark:text-blue-400">{hub.icon}</div>
              <ArrowLeft className="h-4 w-4 text-slate-300 transition group-hover:-translate-x-1 group-hover:text-blue-500" />
            </div>
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">{hub.title}</h3>
            <p className="mt-1.5 text-xs leading-6 text-slate-500 dark:text-slate-400">{hub.description}</p>
            <p className="mt-3 text-xs font-semibold text-blue-600 dark:text-blue-400">{hub.stat}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}