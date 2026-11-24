/**
 * مدیریت مدل‌ها — CRUD، مدل پیش‌فرض/جایگزین، هزینه توکن (PRD §7).
 */
'use client';

import { useEffect, useState } from 'react';
import { Pencil, Bot, Trash2, Star } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { DataTable } from '@/components/admin/DataTable';
import type { Column } from '@/components/admin/DataTable';
import { Button, Badge, Input, Select, Toggle } from '@/components/ui';
import { ConfirmDialog, Modal, useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList, useFormState } from '@/lib/hooks';
import { fmtNum } from '@/lib/format';
import type { AdminModel, AdminProvider } from '@/types/entities';

interface ModelFormValues extends Record<string, unknown> {
  provider_id: string;
  model_identifier: string;
  display_name_fa: string;
  is_active: boolean;
  is_default: boolean;
  input_cost_per_k_tokens: string;
  output_cost_per_k_tokens: string;
  max_context_tokens: string;
  fallback_model_id: string;
}

const emptyForm: ModelFormValues = {
  provider_id: '', model_identifier: '', display_name_fa: '',
  is_active: true, is_default: false,
  input_cost_per_k_tokens: '0', output_cost_per_k_tokens: '0',
  max_context_tokens: '32000', fallback_model_id: '',
};

export default function ModelsPage() {
  const toast = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<AdminModel | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [providers, setProviders] = useState<AdminProvider[]>([]);

  const { data, loading, reload } = useApiList<AdminModel>(() => api.models.list(), [], ['models']);

  useEffect(() => {
    api.providers.list().then((p) => setProviders(p.items)).catch(() => undefined);
  }, []);

  const form = useFormState<ModelFormValues>(emptyForm);

  function openCreate() {
    setEditingId(null);
    form.reset();
    setModalOpen(true);
  }

  function openEdit(model: AdminModel) {
    setEditingId(model.id);
    form.reset({
      provider_id: model.provider_id,
      model_identifier: model.model_identifier,
      display_name_fa: model.display_name_fa,
      is_active: Boolean(model.is_active),
      is_default: Boolean(model.is_default),
      input_cost_per_k_tokens: String(model.input_cost_per_k_tokens ?? '0'),
      output_cost_per_k_tokens: String(model.output_cost_per_k_tokens ?? '0'),
      max_context_tokens: String(model.max_context_tokens ?? '32000'),
      fallback_model_id: model.fallback_model_id || '',
    } as ModelFormValues);
    setModalOpen(true);
  }

  async function submit() {
    const errors: Partial<Record<keyof ModelFormValues, string>> = {};
    if (!form.values.provider_id) errors.provider_id = 'انتخاب Provider الزامی است.';
    if (!String(form.values.model_identifier).trim()) errors.model_identifier = 'شناسه مدل الزامی است.';
    if (!String(form.values.display_name_fa).trim()) errors.display_name_fa = 'نام نمایشی الزامی است.';
    if (Object.keys(errors).length) {
      form.setErrors(errors);
      return;
    }
    form.setSubmitting(true);
    try {
      const payload = {
        provider_id: form.values.provider_id,
        model_identifier: String(form.values.model_identifier).trim(),
        display_name_fa: String(form.values.display_name_fa).trim(),
        is_active: form.values.is_active,
        is_default: form.values.is_default,
        input_cost_per_k_tokens: Number(form.values.input_cost_per_k_tokens) || 0,
        output_cost_per_k_tokens: Number(form.values.output_cost_per_k_tokens) || 0,
        max_context_tokens: Number(form.values.max_context_tokens) || 32000,
        fallback_model_id: form.values.fallback_model_id || null,
      };
      if (editingId) {
        await api.models.update(editingId, payload);
        toast.success('مدل بروزرسانی شد.');
      } else {
        await api.models.create(payload);
        toast.success('مدل جدید ایجاد شد.');
      }
      setModalOpen(false);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره مدل ناموفق بود.');
    } finally {
      form.setSubmitting(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await api.models.remove(deleting.id);
      toast.success('مدل حذف شد.');
      setDeleting(null);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'حذف مدل ناموفق بود.');
    } finally {
      setDeleteLoading(false);
    }
  }

  const columns: Column<AdminModel>[] = [
    {
      key: 'name',
      header: 'مدل',
      render: (m) => (
        <div className="flex items-center gap-2">
          {Boolean(m.is_default) && <Star className="h-4 w-4 fill-amber-400 text-amber-400" title="مدل پیش‌فرض" />}
          <div>
            <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{m.display_name_fa}</p>
            <p className="text-xs text-slate-400" dir="ltr">{m.model_identifier}</p>
          </div>
        </div>
      ),
    },
    { key: 'provider', header: 'Provider', render: (m) => providers.find((p) => p.id === m.provider_id)?.name || '—' },
    {
      key: 'cost',
      header: 'هزینه توکن (per 1K)',
      render: (m) => (
        <span className="text-xs text-slate-500 dark:text-slate-400" dir="ltr">
          ${Number(m.input_cost_per_k_tokens).toFixed(3)} / ${Number(m.output_cost_per_k_tokens).toFixed(3)}
        </span>
      ),
    },
    { key: 'context', header: 'کانتکست', render: (m) => `${fmtNum(m.max_context_tokens)}` },
    { key: 'status', header: 'وضعیت', render: (m) => <Badge tone={m.is_active ? 'success' : 'danger'}>{m.is_active ? 'فعال' : 'غیرفعال'}</Badge> },
  ];

  return (
    <div>
      <PageHeader
        title="مدیریت مدل‌ها"
        description="مدل‌های مجاز، مدل پیش‌فرض سامانه و هزینه هر مدل"
        actions={<Button icon={<Bot className="h-4 w-4" />} onClick={openCreate}>مدل جدید</Button>}
      />

      <DataTable columns={columns} rows={data?.items || []} loading={loading} rowKey={(m) => m.id}
        rowActions={(m) => (
          <div className="flex items-center gap-1">
            <button onClick={() => openEdit(m)} className="rounded-lg p-1.5 text-slate-400 hover:bg-blue-500/10 hover:text-blue-500" title="ویرایش">
              <Pencil className="h-4 w-4" />
            </button>
            <button onClick={() => setDeleting(m)} className="rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-500" title="حذف">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        )}
      />

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingId ? 'ویرایش مدل' : 'ایجاد مدل جدید'}
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)} disabled={form.submitting}>انصراف</Button>
            <Button onClick={submit} loading={form.submitting}>{editingId ? 'ذخیره تغییرات' : 'ایجاد مدل'}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            label="Provider *"
            value={String(form.values.provider_id)}
            onChange={(e) => form.setField('provider_id', e.target.value)}
            options={providers.map((p) => ({ value: p.id, label: p.name }))}
            placeholder="انتخاب Provider"
            error={form.errors.provider_id}
          />
          <Input label="شناسه مدل *" dir="ltr" placeholder="gpt-4o / claude-sonnet-4-5"
            value={String(form.values.model_identifier)} onChange={(e) => form.setField('model_identifier', e.target.value)} error={form.errors.model_identifier} />
          <div className="sm:col-span-2">
            <Input label="نام نمایشی (فارسی) *" value={String(form.values.display_name_fa)}
              onChange={(e) => form.setField('display_name_fa', e.target.value)} error={form.errors.display_name_fa} />
          </div>
          <Input label="هزینه ورودی (USD per 1K)" type="number" step="0.001" dir="ltr"
            value={String(form.values.input_cost_per_k_tokens)} onChange={(e) => form.setField('input_cost_per_k_tokens', e.target.value)} />
          <Input label="هزینه خروجی (USD per 1K)" type="number" step="0.001" dir="ltr"
            value={String(form.values.output_cost_per_k_tokens)} onChange={(e) => form.setField('output_cost_per_k_tokens', e.target.value)} />
          <Input label="حداکثر کانتکست (توکن)" type="number" dir="ltr"
            value={String(form.values.max_context_tokens)} onChange={(e) => form.setField('max_context_tokens', e.target.value)} />
          <Select
            label="مدل جایگزین (Fallback)"
            value={String(form.values.fallback_model_id)}
            onChange={(e) => form.setField('fallback_model_id', e.target.value)}
            options={(data?.items || []).filter((m) => m.id !== editingId).map((m) => ({ value: m.id, label: m.display_name_fa }))}
            placeholder="بدون جایگزین"
          />
          <div className="space-y-2 sm:col-span-2">
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <Toggle checked={Boolean(form.values.is_active)} onChange={(v) => form.setField('is_active', v)} label="فعال باشد" />
            </div>
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <Toggle checked={Boolean(form.values.is_default)} onChange={(v) => form.setField('is_default', v)} label="مدل پیش‌فرض سامانه باشد" />
            </div>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="حذف مدل"
        message={`آیا از حذف مدل «${deleting?.display_name_fa}» مطمئن هستید؟`}
        confirmLabel="حذف مدل"
        danger
        loading={deleteLoading}
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}