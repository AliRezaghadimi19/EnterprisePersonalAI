/**
 * تنظیمات Active Directory — فرم کامل + تست اتصال (PRD §3/§5).
 */
'use client';

import { useEffect, useState } from 'react';
import { Globe, KeyRound, PlugZap } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Button, Card, Input, Toggle, Badge } from '@/components/ui';
import { useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { ROLE_LABELS } from '@/lib/constants';
import type { ActiveDirectoryConfig } from '@/types';

export default function AdSettingsPage() {
  const toast = useToast();
  const { isSuperAdmin } = useAuth();
  const [config, setConfig] = useState<ActiveDirectoryConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [bindPassword, setBindPassword] = useState('');
  const [allowedGroupsText, setAllowedGroupsText] = useState('');
  const [mappingsText, setMappingsText] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const cfg = await api.adSettings.get();
        setConfig(cfg);
        setAllowedGroupsText((cfg.allowed_groups || []).join(', '));
        setMappingsText(
          Object.entries(cfg.group_role_mapping || {})
            .map(([group, role]) => `${group}=${role}`)
            .join('\n')
        );
      } catch (e) {
        toast.error(e instanceof ApiError ? e.message : 'دریافت تنظیمات AD ناموفق بود.');
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function collectBody(): Record<string, unknown> {
    if (!config) return {};
    const mapping: Record<string, string> = {};
    for (const line of mappingsText.split('\n')) {
      const [group, role] = line.split('=').map((s) => s.trim());
      if (group && role) mapping[group] = role;
    }
    const body: Record<string, unknown> = {
      is_enabled: config.is_enabled,
      server_host: config.server_host,
      port: Number(config.port) || 389,
      port_ssl: Number(config.port_ssl) || 636,
      use_ssl: config.use_ssl,
      domain_name: config.domain_name,
      base_dn: config.base_dn,
      user_search_base: config.user_search_base || '',
      group_search_base: config.group_search_base || '',
      bind_dn: config.bind_dn || '',
      allowed_groups: allowedGroupsText.split(',').map((g) => g.trim()).filter(Boolean),
      group_role_mapping: mapping,
      auto_provision: config.auto_provision,
    };
    if (bindPassword) body.bind_password = bindPassword;
    return body;
  }

  async function save() {
    setSaving(true);
    try {
      await api.adSettings.update(collectBody());
      toast.success('تنظیمات اکتیو دایرکتوری ذخیره شد.');
      setBindPassword('');
      const cfg = await api.adSettings.get();
      setConfig(cfg);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره تنظیمات ناموفق بود.');
    } finally {
      setSaving(false);
    }
  }

  async function testConnection() {
    setTesting(true);
    try {
      const body = collectBody();
      const result = await api.adSettings.testConnection({
        server_host: body.server_host,
        port: body.port,
        use_ssl: body.use_ssl,
      });
      if (result.success) toast.success(result.message || 'اتصال به دامنه‌کنترلر برقرار است.');
      else toast.error(result.message || 'اتصال برقرار نشد.');
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'تست اتصال ناموفق بود.');
    } finally {
      setTesting(false);
    }
  }

  if (loading) {
    return <p className="py-20 text-center text-sm text-slate-400">در حال بارگذاری تنظیمات…</p>;
  }

  if (!config) {
    return <p className="py-20 text-center text-sm text-slate-400">تنظیمات AD یافت نشد.</p>;
  }

  const set = <K extends keyof ActiveDirectoryConfig>(key: K, value: ActiveDirectoryConfig[K]) =>
    setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));

  return (
    <div>
      <PageHeader
        title="تنظیمات Active Directory"
        description="احراز هویت سازمانی از طریق LDAP/LDAPS"
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" icon={<PlugZap className="h-4 w-4" />} onClick={testConnection} loading={testing}>تست اتصال</Button>
            <Button onClick={save} loading={saving} disabled={!isSuperAdmin}>ذخیره تنظیمات</Button>
          </div>
        }
      />

      {!isSuperAdmin && (
        <p className="mb-4 text-xs text-amber-500">ویرایش تنظیمات اکتیو دایرکتوری منحصر به مدیر کل سامانه است.</p>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="اتصال به دامنه‌کنترلر">
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <Toggle checked={config.is_enabled} onChange={(v) => set('is_enabled', v)} label="احراز هویت AD فعال باشد" />
            </div>
            <Input label="آدرس Domain Controller" dir="ltr" value={config.server_host || ''} onChange={(e) => set('server_host', e.target.value)} />
            <div className="grid grid-cols-2 gap-4">
              <Input label="پورت LDAP" type="number" dir="ltr" value={String(config.port ?? 389)} onChange={(e) => set('port', Number(e.target.value))} />
              <Input label="پورت LDAPS" type="number" dir="ltr" value={String(config.port_ssl ?? 636)} onChange={(e) => set('port_ssl', Number(e.target.value))} />
            </div>
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <Toggle checked={config.use_ssl} onChange={(v) => set('use_ssl', v)} label="استفاده از SSL/TLS (LDAPS)" />
            </div>
            <Input label="نام دامنه" dir="ltr" placeholder="enterprise.local" value={config.domain_name || ''} onChange={(e) => set('domain_name', e.target.value)} />
          </div>
        </Card>

        <Card title="ساختار دایرکتوری">
          <div className="space-y-4">
            <Input label="Base DN" dir="ltr" placeholder="dc=enterprise,dc=local" value={config.base_dn || ''} onChange={(e) => set('base_dn', e.target.value)} />
            <Input label="User Search Base" dir="ltr" placeholder="ou=users,dc=enterprise,dc=local" value={config.user_search_base || ''} onChange={(e) => set('user_search_base', e.target.value)} />
            <Input label="Group Search Base" dir="ltr" placeholder="ou=groups,dc=enterprise,dc=local" value={config.group_search_base || ''} onChange={(e) => set('group_search_base', e.target.value)} />
            <Input label="Bind Account (DN)" dir="ltr" placeholder="cn=svc-ai,cn=users,..." value={config.bind_dn || ''} onChange={(e) => set('bind_dn', e.target.value)} />
            <Input
              label={config.has_bind_password ? 'رمز Bind جدید (اختیاری)' : 'رمز Bind'}
              dir="ltr"
              type="password"
              value={bindPassword}
              onChange={(e) => setBindPassword(e.target.value)}
              hint={config.has_bind_password ? 'رمز فعلی ذخیره و رمزنگاری شده است.' : undefined}
            />
          </div>
        </Card>

        <Card title="گروه‌های مجاز ورود">
          <Input
            placeholder="مثال: Domain Users, AI-Access, IT-Staff"
            value={allowedGroupsText}
            onChange={(e) => setAllowedGroupsText(e.target.value)}
            hint="گروه‌های AD مجاز به ورود — جداشده با ویرگول. خالی = همه گروه‌ها"
          />
        </Card>

        <Card title="نگاشت گروه‌های AD به نقش‌های سامانه">
          <textarea
            dir="ltr"
            rows={6}
            className="w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3.5 py-2.5 font-mono text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            placeholder={'AI-Admins=super_admin\nIT-Staff=system_admin\nDomain Users=normal_subscriber'}
            value={mappingsText}
            onChange={(e) => setMappingsText(e.target.value)}
          />
          <p className="mt-2 text-xs text-slate-400">هر خط: «نام گروه AD=نقش سامانه». نقش‌های موجود: {Object.entries(ROLE_LABELS).map(([k, v]) => `${k} (${v})`).join('، ')}</p>
        </Card>

        <Card title="تدارکات کاربر" className="lg:col-span-2">
          <div className="max-w-md rounded-xl border border-slate-200 dark:border-slate-700 p-3">
            <Toggle checked={config.auto_provision} onChange={(v) => set('auto_provision', v)} label="ایجاد خودکار پروفایل کاربر پس از ورود موفق AD" />
          </div>
          <p className="mt-3 text-xs leading-6 text-slate-400">
            رمز عبور کاربران AD هرگز در سامانه ذخیره نمی‌شود؛ احراز هویت مستقیماً روی دامنه‌کنترلر انجام می‌گیرد.
            {config.updated_at && <> آخرین بروزرسانی: <Badge tone="neutral">{new Date(config.updated_at).toLocaleDateString('fa-IR')}</Badge></>}
          </p>
        </Card>
      </div>
    </div>
  );
}