/**
 * مدیریت Providerها — CRUD + API key + تست اتصال (PRD §7).
 */
'use client';

import { useState } from 'react';
import { Pencil, Plug, PlugZap, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { DataTable } from '@/components/admin/DataTable';
import type { Column } from '@/components/admin/DataTable';
import { Button, Badge, Input, Select, Toggle } from '@/components/ui';
import { ConfirmDialog, Modal, useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList, useFormState } from '@/lib/hooks';
import type { AdminProvider } from '@/types/entities';

const PROVIDER_TYPES = [
  { value: 'OPENAI', label: 'OpenAI' },
  { value: 'ANTHROPIC', label: 'Anthropic Claude' },
  { value: 'GEMINI', label: 'Google Gemini' },
  { value: 'OPENAI_COMPATIBLE', label: 'سازگار با OpenAI' },
  { value: 'CUSTOM', label: 'سفارشی' },
];

interface ProviderFormValues extends Record<string, unknown> {
  name: string;
  provider_type: string;
  base_url: string;
  api_key: string;
  is_active: boolean;
}

const emptyForm: ProviderFormValues = { name: '', provider_type: 'OPENAI', base_url: '', api_key: '', is_active: true };

export default function ProvidersPage() {
  const toast = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<AdminProvider | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  const { data, loading, reload } = useApiList<AdminProvider>(() => api.providers.list(), [], ['providers']);
  const form = useFormState<ProviderFormValues>(emptyForm);

  function openCreate() {
    setEditingId(null);
    form.reset();
    setModalOpen(true);
  }

  function openEdit(provider: AdminProvider) {
    setEditingId(provider.id);
    form.reset({
      name: provider.name,
      provider_type: provider.provider_type,
      base_url: provider.base_url || '',
      api_key: '', // write-only; never displayed
      is_active: Boolean(provider.is_active),
    } as ProviderFormValues);
    setModalOpen(true);
  }

  async function submit() {
    const errors: Partial<Record<keyof ProviderFormValues, string>> = {};
    if (!String(form.values.name).trim()) errors.name = 'نام Provider الزامی است.';
    if (!editingId && !String(form.values.api_key).trim()) errors.api_key = 'کلید API الزامی است.';
    if (Object.keys(errors).length) {
      form.setErrors(errors);
      return;
    }
    form.setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        name: String(form.values.name).trim(),
        provider_type: form.values.provider_type,
        base_url: String(form.values.base_url) || null,
        is_active: form.values.is_active,
      };
      if (String(form.values.api_key).trim()) payload.api_key = String(form.values.api_key).trim();
      if (editingId) {
        await api.providers.update(editingId, payload);
        toast.success('Provider بروزرسانی شد.');
      } else {
        await api.providers.create(payload);
        toast.success('Provider جدید ایجاد شد.');
      }
      setModalOpen(false);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره Provider ناموفق بود.');
    } finally {
      form.setSubmitting(false);
    }
  }

  async function testConnection(provider: AdminProvider) {
    setTestingId(provider.id);
    try {
      const result = await api.providers.testConnection({ provider_id: provider.id });
      if (result.success) toast.success(`اتصال «${provider.name}» برقرار است.`);
      else toast.error(result.message || 'اتصال ناموفق بود.');
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'تست اتصال ناموفق بود.');
    } finally {
      setTestingId(null);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await api.providers.remove(deleting.id);
      toast.success('Provider حذف شد.');
      setDeleting(null);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'حذف Provider ناموفق بود.');
    } finally {
      setDeleteLoading(false);
    }
  }

  const columns: Column<AdminProvider>[] = [
    {
      key: 'name',
      header: 'Provider',
      render: (p) => (
        <div>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{p.name}</p>
          {p.base_url && <p className="text-xs text-slate-400" dir="ltr">{p.base_url}</p>}
        </div>
      ),
    },
    { key: 'type', header: 'نوع', render: (p) => <Badge tone="neutral">{PROVIDER_TYPES.find((t) => t.value === p.provider_type)?.label || p.provider_type}</Badge> },
    { key: 'key', header: 'کلید API', render: (p) => <span className="text-xs text-slate-400">{p.has_api_key ? '🔑 ذخیره شده' : 'ثبت نشده'}</span> },
    { key: 'status', header: 'وضعیت', render: (p) => <Badge tone={p.is_active ? 'success' : 'danger'}>{p.is_active ? 'فعال' : 'غیرفعال'}</Badge> },
  ];

  return (
    <div>
      <PageHeader
        title="مدیریت Providerها"
        description="اتصال به سرویس‌دهندگان هوش مصنوعی — کلیدها رمزنگاری‌شده ذخیره می‌شوند و هرگز به مرورگر ارسال نمی‌گردند"
        actions={<Button icon={<Plug className="h-4 w-4" />} onClick={openCreate}>Provider جدید</Button>}
      />

      <DataTable columns={columns} rows={data?.items || []} loading={loading} rowKey={(p) => p.id}
        rowActions={(p) => (
          <div className="flex items-center gap-1">
            <button
              onClick={() => testConnection(p)}
              disabled={testingId === p.id}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-emerald-500/10 hover:text-emerald-500 disabled:opacity-40"
              title="تست اتصال"
            >
              <PlugZap className="h-4 w-4" />
            </button>
            <button onClick={() => openEdit(p)} className="rounded-lg p-1.5 text-slate-400 hover:bg-blue-500/10 hover:text-blue-500" title="ویرایش">
              <Pencil className="h-4 w-4" />
            </button>
            <button onClick={() => setDeleting(p)} className="rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-500" title="حذف">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        )}
      />

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingId ? 'ویرایش Provider' : 'ایجاد Provider جدید'}
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)} disabled={form.submitting}>انصراف</Button>
            <Button onClick={submit} loading={form.submitting}>{editingId ? 'ذخیره تغییرات' : 'ایجاد Provider'}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="نام *" value={String(form.values.name)} onChange={(e) => form.setField('name', e.target.value)} error={form.errors.name} />
          <Select label="نوع سرویس" value={String(form.values.provider_type)} onChange={(e) => form.setField('provider_type', e.target.value)} options={PROVIDER_TYPES} />
          <div className="sm:col-span-2">
            <Input label="آدرس پایه (Endpoint)" dir="ltr" placeholder="https://api.openai.com/v1"
              value={String(form.values.base_url)} onChange={(e) => form.setField('base_url', e.target.value)}
              hint="برای نوع سفارشی/سازگار الزامی است" />
          </div>
          <div className="sm:col-span-2">
            <Input
              label={editingId ? 'کلید API جدید (اختیاری)' : 'کلید API *'}
              dir="ltr"
              type="password"
              value={String(form.values.api_key)}
              onChange={(e) => form.setField('api_key', e.target.value)}
              error={form.errors.api_key}
              hint={editingId ? 'کلید قبلی ذخیره شده است؛ برای تغییر، کلید جدید وارد کنید.' : 'رمزنگاری‌شده ذخیره می‌شود.'}
            />
          </div>
          <div className="sm:col-span-2 rounded-xl border border-slate-200 dark:border-slate-700 p-3">
            <Toggle checked={Boolean(form.values.is_active)} onChange={(v) => form.setField('is_active', v)} label="فعال باشد" />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="حذف Provider"
        message={`آیا از حذف «${deleting?.name}» مطمئن هستید؟ مدل‌های وابسته به این Provider غیرقابل استفاده می‌شوند.`}
        confirmLabel="حذف Provider"
        danger
        loading={deleteLoading}
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}