/**
 * تنظیمات سامانه — ۶ کلید سراسری (فقط مدیر کل) (PRD §19).
 */
'use client';

import { useEffect, useState } from 'react';
import { Settings } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Button, Card, Input, Select, Toggle, Badge } from '@/components/ui';
import { useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { POLICY_LABELS } from '@/lib/constants';
import type { SystemSettings } from '@/types';

export default function SystemSettingsPage() {
  const toast = useToast();
  const { isSuperAdmin } = useAuth();
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.settings.get().then((s) => setSettings(s as SystemSettings)).catch((e: unknown) => toast.error(e instanceof ApiError ? e.message : 'دریافت تنظیمات ناموفق بود.'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const set = <K extends keyof SystemSettings>(key: K, value: SystemSettings[K]) =>
    setSettings((prev) => (prev ? { ...prev, [key]: value } : prev));

  async function save() {
    if (!settings) return;
    setSaving(true);
    try {
      const updated = (await api.settings.update(settings)) as SystemSettings;
      setSettings(updated);
      toast.success('تنظیمات سامانه ذخیره شد.');
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره تنظیمات ناموفق بود.');
    } finally {
      setSaving(false);
    }
  }

  if (!settings) return <p className="py-20 text-center text-sm text-slate-400">در حال بارگذاری…</p>;

  return (
    <div>
      <PageHeader
        title="تنظیمات سامانه"
        description="پیکربندی سراسری احراز هویت، پاسخ‌گویی، زبان و امنیت"
        actions={<Button icon={<Settings className="h-4 w-4" />} onClick={save} loading={saving} disabled={!isSuperAdmin}>ذخیره تنظیمات</Button>}
      />

      {!isSuperAdmin && <p className="mb-4 text-xs text-amber-500">ویرایش تنظیمات سامانه منحصر به مدیر کل است.</p>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="روش‌های احراز هویت">
          <Select
            label="حالت احراز هویت مجاز"
            value={settings.auth_mode}
            onChange={(e) => set('auth_mode', e.target.value as SystemSettings['auth_mode'])}
            disabled={!isSuperAdmin}
            options={[
              { value: 'BOTH', label: 'هر دو روش (AD + داخلی)' },
              { value: 'LOCAL_ONLY', label: 'فقط کاربران داخلی' },
              { value: 'AD_ONLY', label: 'فقط Active Directory' },
            ]}
          />
          <p className="mt-2 text-xs text-slate-400">تعیین می‌کند کاربران از چه روش‌هایی بتوانند وارد شوند.</p>
        </Card>

        <Card title="هوش مصنوعی">
          <div className="space-y-4">
            <Select
              label="سیاست پاسخ‌گویی پیش‌فرض"
              value={settings.default_response_policy}
              onChange={(e) => set('default_response_policy', e.target.value as SystemSettings['default_response_policy'])}
              disabled={!isSuperAdmin}
              options={Object.entries(POLICY_LABELS).map(([value, label]) => ({ value, label }))}
            />
            <Select
              label="زبان پیش‌فرض پاسخ هوش مصنوعی"
              value={settings.default_ai_language}
              onChange={(e) => set('default_ai_language', e.target.value)}
              disabled={!isSuperAdmin}
              options={[
                { value: 'fa', label: 'فارسی' },
                { value: 'en', label: 'انگلیسی' },
              ]}
            />
          </div>
        </Card>

        <Card title="فایل‌ها">
          <div className="space-y-4">
            <Input
              label="حداکثر حجم فایل (MB)"
              type="number"
              dir="ltr"
              value={String(settings.max_file_size_mb)}
              onChange={(e) => set('max_file_size_mb', Number(e.target.value) || 25)}
              disabled={!isSuperAdmin}
            />
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <Toggle
                checked={settings.allow_file_upload_globally}
                onChange={(v) => set('allow_file_upload_globally', v)}
                label="آپلود فایل به‌صورت سراسری مجاز باشد"
              />
            </div>
            <p className="text-xs text-slate-400">تنظیمات تفصیلی‌تر در صفحه <a href="/admin/file-settings" className="text-blue-600 dark:text-blue-400 hover:underline">تنظیمات فایل‌ها</a>.</p>
          </div>
        </Card>

        <Card title="امنیت جلسه">
          <Input
            label="مدت انقضای جلسه (دقیقه)"
            type="number"
            dir="ltr"
            value={String(settings.session_timeout_minutes)}
            onChange={(e) => set('session_timeout_minutes', Number(e.target.value) || 480)}
            disabled={!isSuperAdmin}
            hint="پس از این مدت بی‌فعالیتی، کاربر به‌صورت خودکار خارج می‌شود."
          />
        </Card>
      </div>
    </div>
  );
}