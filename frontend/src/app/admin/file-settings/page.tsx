/**
 * تنظیمات فایل‌ها — سراسری + per-group (PRD §10/§14).
 */
'use client';

import { useEffect, useState } from 'react';
import { Paperclip, Save } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Button, Card, Input, Toggle, Badge, cn } from '@/components/ui';
import { Modal, useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList } from '@/lib/hooks';
import { useAuth } from '@/lib/auth-context';
import { fmtNum } from '@/lib/format';
import type { AdminGroup } from '@/types/entities';
import type { SystemSettings } from '@/types';

const FILE_TYPES = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'ppt', 'pptx', 'jpg', 'png'];

export default function FileSettingsPage() {
  const toast = useToast();
  const { isSuperAdmin } = useAuth();
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [savingGlobal, setSavingGlobal] = useState(false);
  const [editingGroup, setEditingGroup] = useState<AdminGroup | null>(null);
  const [groupTypes, setGroupTypes] = useState<string[]>([]);
  const [groupMaxSize, setGroupMaxSize] = useState('25');
  const [savingGroup, setSavingGroup] = useState(false);

  const { data: groups, reload: reloadGroups } = useApiList<AdminGroup>(() => api.groups.list(), [], ['groups']);

  useEffect(() => {
    api.settings.get().then(setSettings).catch(() => undefined);
  }, []);

  async function saveGlobal() {
    if (!settings) return;
    setSavingGlobal(true);
    try {
      const updated = await api.settings.update({
        allow_file_upload_globally: settings.allow_file_upload_globally,
        max_file_size_mb: settings.max_file_size_mb,
      });
      setSettings(updated);
      toast.success('تنظیمات سراسری فایل ذخیره شد.');
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره ناموفق بود.');
    } finally {
      setSavingGlobal(false);
    }
  }

  function openGroup(group: AdminGroup) {
    setEditingGroup(group);
    const types = group.allowed_file_types;
    setGroupTypes(Array.isArray(types) ? types : typeof types === 'string' && types ? types.split(',').map((t) => t.trim()) : []);
    setGroupMaxSize(String(group.max_file_size_mb ?? 25));
  }

  async function saveGroup() {
    if (!editingGroup) return;
    setSavingGroup(true);
    try {
      await api.groups.update(editingGroup.id, {
        max_file_size_mb: Number(groupMaxSize) || 25,
        allowed_file_types: groupTypes,
      });
      toast.success(`سیاست فایل گروه «${editingGroup.name}» ذخیره شد.`);
      setEditingGroup(null);
      await reloadGroups();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره ناموفق بود.');
    } finally {
      setSavingGroup(false);
    }
  }

  function toggleType(type: string) {
    setGroupTypes((prev) => (prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]));
  }

  return (
    <div>
      <PageHeader title="تنظیمات فایل‌ها" description="سیاست آپلود فایل در چت — سراسری و به تفکیک گروه" />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="تنظیمات سراسری" actions={isSuperAdmin ? undefined : <Badge tone="warn">فقط مدیر کل</Badge>}>
          {settings && (
            <div className="space-y-4">
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
                <Toggle
                  checked={settings.allow_file_upload_globally}
                  onChange={(v) => setSettings((prev) => (prev ? { ...prev, allow_file_upload_globally: v } : prev))}
                  label="آپلود فایل مجاز باشد"
                />
              </div>
              <Input
                label="حداکثر حجم فایل سراسری (MB)"
                type="number"
                dir="ltr"
                value={String(settings.max_file_size_mb)}
                onChange={(e) => setSettings((prev) => (prev ? { ...prev, max_file_size_mb: Number(e.target.value) || 25 } : prev))}
                disabled={!isSuperAdmin}
              />
              <Button icon={<Save className="h-4 w-4" />} onClick={saveGlobal} loading={savingGlobal} disabled={!isSuperAdmin}>ذخیره سراسری</Button>
            </div>
          )}
        </Card>

        <Card title="فرمت‌های مجاز پیشنهادی">
          <div className="flex flex-wrap gap-1.5">
            {FILE_TYPES.map((type) => (
              <span key={type} className="rounded-lg bg-slate-100 dark:bg-slate-700 px-2.5 py-1 text-xs text-slate-600 dark:text-slate-300" dir="ltr">
                {type}
              </span>
            ))}
          </div>
          <p className="mt-3 text-xs leading-6 text-slate-400">
            برای هر گروه می‌توانید زیرمجموعه‌ای از این فرمت‌ها را مجاز کنید. فایل‌ها قبل از ذخیره اعتبارسنجی نوع و حجم می‌شوند.
          </p>
        </Card>
      </div>

      <div className="mt-6">
        <h3 className="mb-3 text-sm font-bold text-slate-700 dark:text-slate-200">سیاست فایل به تفکیک گروه</h3>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(groups?.items || []).map((group) => {
            const types = Array.isArray(group.allowed_file_types) ? group.allowed_file_types : [];
            return (
              <div key={group.id} className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-bold text-slate-700 dark:text-slate-200">{group.name}</p>
                  <Button size="sm" variant="outline" icon={<Paperclip className="h-3.5 w-3.5" />} onClick={() => openGroup(group)}>ویرایش</Button>
                </div>
                <p className="mt-2 text-xs text-slate-400">حداکثر حجم: {fmtNum(group.max_file_size_mb)} MB</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {types.length ? types.map((t) => (
                    <span key={t} className="rounded-md bg-blue-500/10 px-1.5 py-0.5 text-[10px] text-blue-600 dark:text-blue-400" dir="ltr">{t}</span>
                  )) : <span className="text-[11px] text-slate-400">فرمتی تعیین نشده</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <Modal
        open={!!editingGroup}
        onClose={() => setEditingGroup(null)}
        title={`سیاست فایل گروه «${editingGroup?.name || ''}»`}
        footer={
          <>
            <Button variant="outline" onClick={() => setEditingGroup(null)} disabled={savingGroup}>انصراف</Button>
            <Button onClick={saveGroup} loading={savingGroup}>ذخیره</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="حداکثر حجم فایل (MB)"
            type="number"
            dir="ltr"
            value={groupMaxSize}
            onChange={(e) => setGroupMaxSize(e.target.value)}
          />
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-300">فرمت‌های مجاز</p>
            <div className="flex flex-wrap gap-1.5">
              {FILE_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => toggleType(type)}
                  className={cn(
                    'rounded-lg border px-2.5 py-1 text-xs transition',
                    groupTypes.includes(type)
                      ? 'border-blue-500 bg-blue-500/10 text-blue-600 dark:text-blue-400'
                      : 'border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-slate-300'
                  )}
                  dir="ltr"
                >
                  {type}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}