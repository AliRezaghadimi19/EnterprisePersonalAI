/**
 * مدیریت گروه‌ها — CRUD با تنظیمات مستقل سهمیه/سیاست/فایل (PRD §5).
 */
'use client';

import { useEffect, useState } from 'react';
import { Building2, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { DataTable } from '@/components/admin/DataTable';
import type { Column } from '@/components/admin/DataTable';
import { Button, Badge, Input, Select, Textarea, Toggle } from '@/components/ui';
import { ConfirmDialog, Modal, useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList, useFormState } from '@/lib/hooks';
import { fmtNum } from '@/lib/format';
import { POLICY_LABELS } from '@/lib/constants';
import type { AdminGroup, AdminModel } from '@/types/entities';

interface GroupFormValues extends Record<string, unknown> {
  name: string;
  description: string;
  default_policy: string;
  default_model_id: string;
  allow_model_selection: boolean;
  daily_question_limit: string;
  monthly_question_limit: string;
  daily_token_limit: string;
  monthly_token_limit: string;
  max_file_size_mb: string;
  allowed_file_types: string;
}

const emptyForm: GroupFormValues = {
  name: '', description: '', default_policy: 'HYBRID', default_model_id: '',
  allow_model_selection: true, daily_question_limit: '100', monthly_question_limit: '3000',
  daily_token_limit: '200000', monthly_token_limit: '5000000', max_file_size_mb: '25',
  allowed_file_types: 'pdf,docx,txt,csv,xlsx,jpg,png',
};

const FILE_TYPE_OPTIONS = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'ppt', 'pptx', 'jpg', 'png'];

export default function GroupsPage() {
  const toast = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<AdminGroup | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [models, setModels] = useState<AdminModel[]>([]);

  const { data, loading, reload } = useApiList<AdminGroup>(() => api.groups.list(), [], ['groups']);

  useEffect(() => {
    api.models.list().then((m) => setModels(m.items)).catch(() => undefined);
  }, []);

  const form = useFormState<GroupFormValues>(emptyForm);

  function openCreate() {
    setEditingId(null);
    form.reset();
    setModalOpen(true);
  }

  function openEdit(group: AdminGroup) {
    setEditingId(group.id);
    const types = group.allowed_file_types;
    const typesStr = Array.isArray(types) ? types.join(',') : typeof types === 'string' ? types : '';
    form.reset({
      ...emptyForm,
      name: group.name,
      description: group.description || '',
      default_policy: group.default_policy || 'HYBRID',
      default_model_id: group.default_model_id || '',
      allow_model_selection: Boolean(group.allow_model_selection),
      daily_question_limit: String(group.daily_question_limit ?? ''),
      monthly_question_limit: String(group.monthly_question_limit ?? ''),
      daily_token_limit: String(group.daily_token_limit ?? ''),
      monthly_token_limit: String(group.monthly_token_limit ?? ''),
      max_file_size_mb: String(group.max_file_size_mb ?? ''),
      allowed_file_types: typesStr,
    } as GroupFormValues);
    setModalOpen(true);
  }

  async function submit() {
    if (!String(form.values.name).trim()) {
      form.setErrors({ name: 'نام گروه الزامی است.' });
      return;
    }
    form.setSubmitting(true);
    try {
      const v = form.values;
      const types = String(v.allowed_file_types).split(',').map((t) => t.trim()).filter(Boolean);
      const payload = {
        name: String(v.name).trim(),
        description: String(v.description) || null,
        default_policy: v.default_policy,
        default_model_id: v.default_model_id || null,
        allow_model_selection: v.allow_model_selection,
        daily_question_limit: Number(v.daily_question_limit) || 0,
        monthly_question_limit: Number(v.monthly_question_limit) || 0,
        daily_token_limit: Number(v.daily_token_limit) || 0,
        monthly_token_limit: Number(v.monthly_token_limit) || 0,
        max_file_size_mb: Number(v.max_file_size_mb) || 25,
        allowed_file_types: types,
      };
      if (editingId) {
        await api.groups.update(editingId, payload);
        toast.success('گروه با موفقیت بروزرسانی شد.');
      } else {
        await api.groups.create(payload);
        toast.success('گروه جدید ایجاد شد.');
      }
      setModalOpen(false);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره گروه ناموفق بود.');
    } finally {
      form.setSubmitting(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await api.groups.remove(deleting.id);
      toast.success('گروه حذف شد.');
      setDeleting(null);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'حذف گروه ناموفق بود.');
    } finally {
      setDeleteLoading(false);
    }
  }

  const columns: Column<AdminGroup>[] = [
    {
      key: 'name',
      header: 'گروه',
      render: (g) => (
        <div>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{g.name}</p>
          {g.description && <p className="text-xs text-slate-400">{g.description}</p>}
        </div>
      ),
    },
    { key: 'policy', header: 'سیاست پیش‌فرض', render: (g) => <Badge tone="info">{POLICY_LABELS[g.default_policy] || g.default_policy}</Badge> },
    { key: 'members', header: 'اعضا', render: (g) => fmtNum(g.member_count ?? 0) },
    { key: 'daily', header: 'سقف روزانه', render: (g) => `${fmtNum(g.daily_question_limit)} سؤال` },
    { key: 'monthly', header: 'سقف ماهانه', render: (g) => `${fmtNum(g.monthly_question_limit)} سؤال` },
    { key: 'file', header: 'حجم فایل', render: (g) => `${fmtNum(g.max_file_size_mb)} MB` },
  ];

  return (
    <div>
      <PageHeader
        title="مدیریت گروه‌ها"
        description="تعریف گروه‌های سازمانی و تنظیمات مستقل هر گروه"
        actions={<Button icon={<Building2 className="h-4 w-4" />} onClick={openCreate}>گروه جدید</Button>}
      />

      <DataTable columns={columns} rows={data?.items || []} loading={loading} rowKey={(g) => g.id}
        rowActions={(g) => (
          <div className="flex items-center gap-1">
            <button onClick={() => openEdit(g)} className="rounded-lg p-1.5 text-slate-400 hover:bg-blue-500/10 hover:text-blue-500" title="ویرایش">
              <Pencil className="h-4 w-4" />
            </button>
            <button onClick={() => setDeleting(g)} className="rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-500" title="حذف">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        )}
      />

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingId ? 'ویرایش گروه' : 'ایجاد گروه جدید'}
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)} disabled={form.submitting}>انصراف</Button>
            <Button onClick={submit} loading={form.submitting}>{editingId ? 'ذخیره تغییرات' : 'ایجاد گروه'}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="نام گروه *" value={String(form.values.name)} onChange={(e) => form.setField('name', e.target.value)} error={form.errors.name} />
          <Select
            label="سیاست پاسخ‌گویی پیش‌فرض"
            value={String(form.values.default_policy)}
            onChange={(e) => form.setField('default_policy', e.target.value)}
            options={Object.entries(POLICY_LABELS).map(([value, label]) => ({ value, label }))}
          />
          <div className="sm:col-span-2">
            <Textarea label="توضیحات" rows={2} value={String(form.values.description)} onChange={(e) => form.setField('description', e.target.value)} />
          </div>
          <Select
            label="مدل پیش‌فرض"
            value={String(form.values.default_model_id)}
            onChange={(e) => form.setField('default_model_id', e.target.value)}
            options={models.map((m) => ({ value: m.id, label: m.display_name_fa }))}
            placeholder="انتخاب مدل"
          />
          <div className="flex items-end">
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 w-full">
              <Toggle checked={Boolean(form.values.allow_model_selection)} onChange={(v) => form.setField('allow_model_selection', v)} label="اعضای گروه بتوانند مدل انتخاب کنند" />
            </div>
          </div>

          <div className="sm:col-span-2">
            <p className="mb-2 text-xs font-bold text-slate-500 dark:text-slate-400">سهمیه‌بندی مصرف</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="سقف سؤال روزانه" type="number" dir="ltr" value={String(form.values.daily_question_limit)} onChange={(e) => form.setField('daily_question_limit', e.target.value)} />
              <Input label="سقف سؤال ماهانه" type="number" dir="ltr" value={String(form.values.monthly_question_limit)} onChange={(e) => form.setField('monthly_question_limit', e.target.value)} />
              <Input label="سقف توکن روزانه" type="number" dir="ltr" value={String(form.values.daily_token_limit)} onChange={(e) => form.setField('daily_token_limit', e.target.value)} />
              <Input label="سقف توکن ماهانه" type="number" dir="ltr" value={String(form.values.monthly_token_limit)} onChange={(e) => form.setField('monthly_token_limit', e.target.value)} />
            </div>
          </div>

          <div className="sm:col-span-2">
            <p className="mb-2 text-xs font-bold text-slate-500 dark:text-slate-400">سیاست فایل</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="حداکثر حجم فایل (MB)" type="number" dir="ltr" value={String(form.values.max_file_size_mb)} onChange={(e) => form.setField('max_file_size_mb', e.target.value)} />
              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">فرمت‌های مجاز</p>
                <div className="flex flex-wrap gap-1.5">
                  {FILE_TYPE_OPTIONS.map((type) => {
                    const selected = String(form.values.allowed_file_types).split(',').map((t) => t.trim()).includes(type);
                    return (
                      <button
                        key={type}
                        type="button"
                        onClick={() => {
                          const current = String(form.values.allowed_file_types).split(',').map((t) => t.trim()).filter(Boolean);
                          const next = selected ? current.filter((t) => t !== type) : [...current, type];
                          form.setField('allowed_file_types', next.join(','));
                        }}
                        className={`rounded-lg border px-2.5 py-1 text-xs transition ${
                          selected
                            ? 'border-blue-500 bg-blue-500/10 text-blue-600 dark:text-blue-400'
                            : 'border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-slate-300'
                        }`}
                      >
                        {type}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="حذف گروه"
        message={`آیا از حذف گروه «${deleting?.name}» مطمئن هستید؟ در صورت داشتن عضو، حذف ناموفق خواهد بود.`}
        confirmLabel="حذف گروه"
        danger
        loading={deleteLoading}
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}