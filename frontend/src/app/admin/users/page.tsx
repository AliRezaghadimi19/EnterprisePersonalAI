/**
 * مدیریت کاربران — full CRUD with filters (PRD §4).
 */
'use client';

import { useEffect, useMemo, useState } from 'react';
import { Pencil, Trash2, UserPlus } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { DataTable } from '@/components/admin/DataTable';
import type { Column } from '@/components/admin/DataTable';
import { Button, Badge, Card, Input, Select, Toggle, cn } from '@/components/ui';
import { ConfirmDialog, Modal, useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList, useDebounce, useFormState } from '@/lib/hooks';
import { fmtDate } from '@/lib/format';
import { AUTH_TYPE_LABELS, POLICY_LABELS, ROLE_LABELS } from '@/lib/constants';
import type { AdminUserListItem, AdminGroup, AdminRole, AdminModel } from '@/types/entities';

interface UserFormValues extends Record<string, unknown> {
  username: string;
  password: string;
  first_name: string;
  last_name: string;
  email: string;
  department: string;
  auth_type: 'LOCAL' | 'ACTIVE_DIRECTORY';
  role_id: string;
  group_id: string;
  is_active: boolean;
  expires_at: string;
  default_model_id: string;
  allow_model_selection: boolean;
  override_policy: string;
  custom_daily_limit: string;
  custom_monthly_limit: string;
  can_upload_files: boolean;
}

const emptyForm: UserFormValues = {
  username: '', password: '', first_name: '', last_name: '', email: '', department: '',
  auth_type: 'LOCAL', role_id: '', group_id: '', is_active: true, expires_at: '',
  default_model_id: '', allow_model_selection: true, override_policy: '',
  custom_daily_limit: '', custom_monthly_limit: '', can_upload_files: true,
};

export default function UsersPage() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search);
  const [groupFilter, setGroupFilter] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<AdminUserListItem | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [refs, setRefs] = useState<{ groups: AdminGroup[]; roles: AdminRole[]; models: AdminModel[] }>({ groups: [], roles: [], models: [] });

  const { data, loading, reload } = useApiList<AdminUserListItem>(
    () => api.users.list({
      search: debouncedSearch || undefined,
      group_id: groupFilter || undefined,
      role_id: roleFilter || undefined,
      is_active: statusFilter === '' ? undefined : statusFilter === 'active' ? 1 : 0,
    }),
    [debouncedSearch, groupFilter, roleFilter, statusFilter],
    ['users']
  );

  useEffect(() => {
    (async () => {
      try {
        const [groups, roles, models] = await Promise.all([api.groups.list(), api.roles.list(), api.models.list()]);
        setRefs({ groups: groups.items, roles: roles.items, models: models.items });
      } catch { /* non-blocking */ }
    })();
  }, []);

  const form = useFormState<UserFormValues>(emptyForm);

  function openCreate() {
    setEditingId(null);
    form.reset();
    setModalOpen(true);
  }

  function openEdit(user: AdminUserListItem) {
    setEditingId(user.id);
    form.reset({
      ...emptyForm,
      username: user.username,
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email || '',
      department: user.department || '',
      auth_type: user.auth_type || 'LOCAL',
      role_id: user.role_id || '',
      group_id: user.group_id || '',
      is_active: Boolean(user.is_active),
      expires_at: (user.expires_at || '').slice(0, 10),
      default_model_id: user.default_model_id || '',
      allow_model_selection: user.allow_model_selection === undefined ? true : Boolean(user.allow_model_selection),
      override_policy: user.override_policy || '',
      custom_daily_limit: user.custom_daily_limit != null ? String(user.custom_daily_limit) : '',
      custom_monthly_limit: user.custom_monthly_limit != null ? String(user.custom_monthly_limit) : '',
      can_upload_files: user.can_upload_files === undefined ? true : Boolean(user.can_upload_files),
    } as UserFormValues);
    setModalOpen(true);
  }

  function validate(): Partial<Record<keyof UserFormValues, string>> {
    const errors: Partial<Record<keyof UserFormValues, string>> = {};
    if (!String(form.values.username).trim()) errors.username = 'نام کاربری الزامی است.';
    if (!editingId && !String(form.values.password)) errors.password = 'رمز عبور الزامی است.';
    if (!String(form.values.first_name).trim()) errors.first_name = 'نام الزامی است.';
    if (!String(form.values.last_name).trim()) errors.last_name = 'نام خانوادگی الزامی است.';
    if (form.values.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(form.values.email))) errors.email = 'ایمیل نامعتبر است.';
    return errors;
  }

  async function submit() {
    const errors = validate();
    if (Object.keys(errors).length) {
      form.setErrors(errors);
      return;
    }
    form.setSubmitting(true);
    try {
      const v = form.values;
      const payload: Record<string, unknown> = {
        username: v.username.trim(),
        first_name: v.first_name.trim(),
        last_name: v.last_name.trim(),
        email: v.email || null,
        department: v.department || null,
        auth_type: v.auth_type,
        role_id: v.role_id || null,
        group_id: v.group_id || null,
        is_active: v.is_active,
        expires_at: v.expires_at || null,
        default_model_id: v.default_model_id || null,
        allow_model_selection: v.allow_model_selection,
        override_policy: v.override_policy || null,
        custom_daily_limit: v.custom_daily_limit ? Number(v.custom_daily_limit) : null,
        custom_monthly_limit: v.custom_monthly_limit ? Number(v.custom_monthly_limit) : null,
        can_upload_files: v.can_upload_files,
      };
      if (!editingId) payload.password = v.password;
      if (editingId) {
        await api.users.update(editingId, payload);
        toast.success('کاربر با موفقیت بروزرسانی شد.');
      } else {
        await api.users.create(payload);
        toast.success('کاربر جدید ایجاد شد.');
      }
      setModalOpen(false);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره کاربر ناموفق بود.');
    } finally {
      form.setSubmitting(false);
    }
  }

  async function toggleActive(user: AdminUserListItem) {
    const next = !Boolean(user.is_active);
    try {
      await api.users.update(user.id, { is_active: next });
      toast.success(next ? 'حساب کاربر فعال شد.' : 'حساب کاربر غیرفعال شد.');
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'تغییر وضعیت ناموفق بود.');
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await api.users.remove(deleting.id);
      toast.success('کاربر حذف شد.');
      setDeleting(null);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'حذف کاربر ناموفق بود.');
    } finally {
      setDeleteLoading(false);
    }
  }

  const columns = useMemo<Column<AdminUserListItem>[]>(() => [
    {
      key: 'name',
      header: 'کاربر',
      render: (u) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600/10 text-xs font-bold text-blue-600 dark:text-blue-400">
            {(u.first_name || u.username || '؟').charAt(0)}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{u.first_name} {u.last_name}</p>
            <p className="text-xs text-slate-400" dir="ltr">@{u.username}</p>
          </div>
        </div>
      ),
    },
    { key: 'role', header: 'نقش', render: (u) => <Badge tone="info">{u.role_display_name_fa || '—'}</Badge> },
    { key: 'group', header: 'گروه', render: (u) => u.group_name || <span className="text-slate-400">—</span> },
    {
      key: 'auth',
      header: 'احراز هویت',
      render: (u) => <Badge tone={u.auth_type === 'ACTIVE_DIRECTORY' ? 'violet' as never : 'neutral'}>{AUTH_TYPE_LABELS[u.auth_type] || u.auth_type}</Badge>,
    },
    {
      key: 'status',
      header: 'وضعیت',
      render: (u) => <Badge tone={u.is_active ? 'success' : 'danger'}>{u.is_active ? 'فعال' : 'غیرفعال'}</Badge>,
    },
    { key: 'created', header: 'تاریخ ایجاد', render: (u) => <span className="text-xs text-slate-400">{fmtDate(u.created_at)}</span> },
  ], []);

  return (
    <div>
      <PageHeader
        title="مدیریت کاربران"
        description="ایجاد، ویرایش و مدیریت حساب‌های کاربری سازمان"
        actions={
          <Button icon={<UserPlus className="h-4 w-4" />} onClick={openCreate}>کاربر جدید</Button>
        }
      />

      <DataTable
        columns={columns}
        rows={data?.items || []}
        loading={loading}
        rowKey={(u) => u.id}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="جستجوی نام یا نام کاربری…"
        filters={
          <>
            <Select
              value={groupFilter}
              onChange={(e) => setGroupFilter(e.target.value)}
              options={refs.groups.map((g) => ({ value: g.id, label: g.name }))}
              placeholder="همه گروه‌ها"
              className="!w-40"
            />
            <Select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              options={refs.roles.map((r) => ({ value: r.id, label: r.display_name_fa }))}
              placeholder="همه نقش‌ها"
              className="!w-40"
            />
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
                { value: 'active', label: 'فعال' },
                { value: 'inactive', label: 'غیرفعال' },
              ]}
              placeholder="همه وضعیت‌ها"
              className="!w-36"
            />
          </>
        }
        rowActions={(u) => (
          <div className="flex items-center gap-1">
            <button onClick={() => openEdit(u)} className="rounded-lg p-1.5 text-slate-400 hover:bg-blue-500/10 hover:text-blue-500" title="ویرایش">
              <Pencil className="h-4 w-4" />
            </button>
            <button
              onClick={() => toggleActive(u)}
              className={cn('rounded-lg px-2 py-1 text-xs', u.is_active ? 'text-red-500 hover:bg-red-500/10' : 'text-emerald-500 hover:bg-emerald-500/10')}
              title={u.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}
            >
              {u.is_active ? 'غیرفعال' : 'فعال'}
            </button>
            <button onClick={() => setDeleting(u)} className="rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-500" title="حذف">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        )}
      />

      {/* Create/Edit modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingId ? 'ویرایش کاربر' : 'ایجاد کاربر جدید'}
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)} disabled={form.submitting}>انصراف</Button>
            <Button onClick={submit} loading={form.submitting}>{editingId ? 'ذخیره تغییرات' : 'ایجاد کاربر'}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="نام *" value={String(form.values.first_name)} onChange={(e) => form.setField('first_name', e.target.value)} error={form.errors.first_name} />
          <Input label="نام خانوادگی *" value={String(form.values.last_name)} onChange={(e) => form.setField('last_name', e.target.value)} error={form.errors.last_name} />
          <Input label="نام کاربری *" dir="ltr" value={String(form.values.username)} onChange={(e) => form.setField('username', e.target.value)} error={form.errors.username} />
          {!editingId && (
            <Input label="رمز عبور *" dir="ltr" type="password" value={String(form.values.password)} onChange={(e) => form.setField('password', e.target.value)} error={form.errors.password} />
          )}
          <Input label="ایمیل" dir="ltr" type="email" value={String(form.values.email)} onChange={(e) => form.setField('email', e.target.value)} error={form.errors.email} />
          <Input label="واحد سازمانی" value={String(form.values.department)} onChange={(e) => form.setField('department', e.target.value)} />
          <Select
            label="نوع احراز هویت"
            value={String(form.values.auth_type)}
            onChange={(e) => form.setField('auth_type', e.target.value)}
            options={[
              { value: 'LOCAL', label: 'داخلی' },
              { value: 'ACTIVE_DIRECTORY', label: 'اکتیو دایرکتوری' },
            ]}
          />
          <Select
            label="نقش"
            value={String(form.values.role_id)}
            onChange={(e) => form.setField('role_id', e.target.value)}
            options={refs.roles.map((r) => ({ value: r.id, label: r.display_name_fa }))}
            placeholder="انتخاب نقش"
          />
          <Select
            label="گروه"
            value={String(form.values.group_id)}
            onChange={(e) => form.setField('group_id', e.target.value)}
            options={refs.groups.map((g) => ({ value: g.id, label: g.name }))}
            placeholder="انتخاب گروه"
          />
          <Input
            label="تاریخ انقضای حساب"
            type="date"
            dir="ltr"
            value={String(form.values.expires_at)}
            onChange={(e) => form.setField('expires_at', e.target.value)}
            hint="خالی = بدون انقضا"
          />
          <Select
            label="سیاست پاسخ‌گویی اختصاصی"
            value={String(form.values.override_policy)}
            onChange={(e) => form.setField('override_policy', e.target.value)}
            options={Object.entries(POLICY_LABELS).map(([value, label]) => ({ value, label }))}
            placeholder="ارث‌بری از گروه"
          />
          <Select
            label="مدل پیش‌فرض"
            value={String(form.values.default_model_id)}
            onChange={(e) => form.setField('default_model_id', e.target.value)}
            options={refs.models.map((m) => ({ value: m.id, label: m.display_name_fa }))}
            placeholder="ارث‌بری از گروه"
          />
          <Input
            label="سقف روزانه اختصاصی (سؤال)"
            type="number"
            dir="ltr"
            value={String(form.values.custom_daily_limit)}
            onChange={(e) => form.setField('custom_daily_limit', e.target.value)}
            hint="خالی = سقف گروه"
          />
          <Input
            label="سقف ماهانه اختصاصی (سؤال)"
            type="number"
            dir="ltr"
            value={String(form.values.custom_monthly_limit)}
            onChange={(e) => form.setField('custom_monthly_limit', e.target.value)}
            hint="خالی = سقف گروه"
          />
          <div className="space-y-2 sm:col-span-2">
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <Toggle checked={Boolean(form.values.is_active)} onChange={(v) => form.setField('is_active', v)} label="حساب فعال باشد" />
            </div>
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <Toggle checked={Boolean(form.values.allow_model_selection)} onChange={(v) => form.setField('allow_model_selection', v)} label="کاربر بتواند مدل را انتخاب کند" />
            </div>
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <Toggle checked={Boolean(form.values.can_upload_files)} onChange={(v) => form.setField('can_upload_files', v)} label="مجوز ارسال فایل" />
            </div>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="حذف کاربر"
        message={`آیا از حذف «${deleting?.first_name} ${deleting?.last_name}» (@${deleting?.username}) مطمئن هستید؟ این عملیات قابل بازگشت نیست.`}
        confirmLabel="حذف کاربر"
        danger
        loading={deleteLoading}
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}