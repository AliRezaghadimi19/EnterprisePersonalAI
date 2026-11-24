/**
 * نقش‌ها و دسترسی‌ها — لیست نقش‌ها، ایجاد/ویرایش نقش سفارشی (فقط مدیر کل).
 */
'use client';

import { useState } from 'react';
import { Pencil, ShieldCheck, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { DataTable } from '@/components/admin/DataTable';
import type { Column } from '@/components/admin/DataTable';
import { Button, Badge, Input, Textarea, cn } from '@/components/ui';
import { ConfirmDialog, Modal, useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList, useFormState } from '@/lib/hooks';
import { useAuth } from '@/lib/auth-context';

interface RoleFormValues extends Record<string, unknown> {
  name: string;
  display_name_fa: string;
  permissions_text: string;
}

const emptyForm: RoleFormValues = { name: '', display_name_fa: '', permissions_text: '' };

const COMMON_PERMISSIONS = [
  'chat:access', 'chat:file_upload', 'chat:select_model',
  'users:read', 'users:write', 'groups:read', 'groups:write',
  'models:read', 'models:write', 'knowledge:read', 'knowledge:write',
  'quotas:read', 'quotas:write', 'logs:read', 'reports:view_team', '*',
];

export default function RolesPage() {
  const toast = useToast();
  const { isSuperAdmin } = useAuth();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<{ id: string; name: string } | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const { data, loading, reload } = useApiList<{ id: string; name: string; display_name_fa: string; permissions: string[]; is_system: boolean | number }>(
    () => api.roles.list(), [], ['roles']
  );

  const form = useFormState<RoleFormValues>(emptyForm);

  function openCreate() {
    setEditingId(null);
    form.reset();
    setModalOpen(true);
  }

  function openEdit(role: { id: string; name: string; display_name_fa: string; permissions: string[] }) {
    setEditingId(role.id);
    form.reset({
      name: role.name,
      display_name_fa: role.display_name_fa,
      permissions_text: (role.permissions || []).join(', '),
    } as RoleFormValues);
    setModalOpen(true);
  }

  async function submit() {
    const errors: Partial<Record<keyof RoleFormValues, string>> = {};
    if (!String(form.values.name).trim()) errors.name = 'شناسه نقش الزامی است.';
    if (!String(form.values.display_name_fa).trim()) errors.display_name_fa = 'نام نمایشی الزامی است.';
    if (Object.keys(errors).length) {
      form.setErrors(errors);
      return;
    }
    form.setSubmitting(true);
    try {
      const permissions = String(form.values.permissions_text).split(',').map((p) => p.trim()).filter(Boolean);
      const payload = { name: String(form.values.name).trim(), display_name_fa: String(form.values.display_name_fa).trim(), permissions };
      if (editingId) {
        await api.roles.update(editingId, payload);
        toast.success('نقش بروزرسانی شد.');
      } else {
        await api.roles.create(payload);
        toast.success('نقش جدید ایجاد شد.');
      }
      setModalOpen(false);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره نقش ناموفق بود.');
    } finally {
      form.setSubmitting(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await api.roles.remove(deleting.id);
      toast.success('نقش حذف شد.');
      setDeleting(null);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'حذف نقش ناموفق بود.');
    } finally {
      setDeleteLoading(false);
    }
  }

  const columns: Column<{ id: string; name: string; display_name_fa: string; permissions: string[]; is_system: boolean | number }>[] = [
    {
      key: 'role',
      header: 'نقش',
      render: (r) => (
        <div>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{r.display_name_fa}</p>
          <p className="text-xs text-slate-400" dir="ltr">{r.name}</p>
        </div>
      ),
    },
    {
      key: 'system',
      header: 'نوع',
      render: (r) => <Badge tone={r.is_system ? 'warn' : 'info'}>{r.is_system ? 'سیستمی' : 'سفارشی'}</Badge>,
    },
    {
      key: 'permissions',
      header: 'مجوزها',
      render: (r) => (
        <div className="flex max-w-md flex-wrap gap-1">
          {(r.permissions || []).slice(0, 6).map((p) => (
            <span key={p} className="rounded-md bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 text-[10px] text-slate-600 dark:text-slate-300" dir="ltr">
              {p}
            </span>
          ))}
          {(r.permissions || []).length > 6 && (
            <span className="text-[10px] text-slate-400">+{r.permissions.length - 6} بیشتر</span>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="نقش‌ها و دسترسی‌ها"
        description="کنترل دسترسی نقش‌محور (RBAC) — ایجاد نقش‌های سفارشی"
        actions={
          <Button icon={<ShieldCheck className="h-4 w-4" />} onClick={openCreate} disabled={!isSuperAdmin}
            title={isSuperAdmin ? 'ایجاد نقش' : 'این عملیات منحصر به مدیر کل است'}>
            نقش جدید
          </Button>
        }
      />

      {!isSuperAdmin && (
        <p className="mb-3 text-xs text-amber-500">ایجاد/ویرایش/حذف نقش منحصر به مدیر کل سامانه است.</p>
      )}

      <DataTable columns={columns} rows={data?.items || []} loading={loading} rowKey={(r) => r.id}
        rowActions={(r) =>
          isSuperAdmin ? (
            <div className="flex items-center gap-1">
              <button onClick={() => openEdit(r)} disabled={Boolean(r.is_system)}
                className={cn('rounded-lg p-1.5', r.is_system ? 'cursor-not-allowed opacity-30' : 'text-slate-400 hover:bg-blue-500/10 hover:text-blue-500')}
                title={r.is_system ? 'نقش سیستمی قابل ویرایش نیست' : 'ویرایش'}>
                <Pencil className="h-4 w-4" />
              </button>
              <button onClick={() => !r.is_system && setDeleting(r)} disabled={Boolean(r.is_system)}
                className={cn('rounded-lg p-1.5', r.is_system ? 'cursor-not-allowed opacity-30' : 'text-slate-400 hover:bg-red-500/10 hover:text-red-500')}
                title={r.is_system ? 'نقش سیستمی قابل حذف نیست' : 'حذف'}>
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ) : null
        }
      />

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingId ? 'ویرایش نقش' : 'ایجاد نقش جدید'}
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)} disabled={form.submitting}>انصراف</Button>
            <Button onClick={submit} loading={form.submitting}>{editingId ? 'ذخیره تغییرات' : 'ایجاد نقش'}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input label="شناسه نقش (انگلیسی) *" dir="ltr" placeholder="مثال: security_auditor"
            value={String(form.values.name)} onChange={(e) => form.setField('name', e.target.value)} error={form.errors.name} />
          <Input label="نام نمایشی (فارسی) *" value={String(form.values.display_name_fa)}
            onChange={(e) => form.setField('display_name_fa', e.target.value)} error={form.errors.display_name_fa} />
          <div>
            <Textarea label="مجوزها (جداشده با ویرگول)" dir="ltr" rows={3}
              value={String(form.values.permissions_text)} onChange={(e) => form.setField('permissions_text', e.target.value)} />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {COMMON_PERMISSIONS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => {
                    const current = String(form.values.permissions_text).split(',').map((s) => s.trim()).filter(Boolean);
                    if (!current.includes(p)) form.setField('permissions_text', [...current, p].join(', '));
                  }}
                  className="rounded-md border border-slate-200 dark:border-slate-600 px-2 py-0.5 text-[10px] text-slate-500 dark:text-slate-400 hover:border-blue-400 hover:text-blue-500"
                  dir="ltr"
                >
                  +{p}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="حذف نقش"
        message={`آیا از حذف نقش «${deleting?.name}» مطمئن هستید؟`}
        confirmLabel="حذف نقش"
        danger
        loading={deleteLoading}
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}