/**
 * پایگاه دانش — دسته‌بندی‌ها (PRD §10).
 */
'use client';

import { BookOpen, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { PageHeader } from '@/components/admin/shell';
import { DataTable } from '@/components/admin/DataTable';
import type { Column } from '@/components/admin/DataTable';
import { Button, Input, Textarea } from '@/components/ui';
import { ConfirmDialog, Modal, useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList, useFormState } from '@/lib/hooks';
import { fmtNum } from '@/lib/format';
import type { KnowledgeCategory, KnowledgeDocument } from '@/types/entities';

interface CategoryFormValues extends Record<string, unknown> {
  name: string;
  description: string;
}

const emptyForm: CategoryFormValues = { name: '', description: '' };

export default function KnowledgePage() {
  const toast = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [deleting, setDeleting] = useState<KnowledgeCategory | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const { data, loading, reload } = useApiList<KnowledgeCategory>(() => api.knowledge.categories.list(), [], ['categories']);
  const docsResult = useApiList<KnowledgeDocument>(() => api.knowledge.documents.list(), [], ['documents']);
  const form = useFormState<CategoryFormValues>(emptyForm);

  async function submit() {
    if (!String(form.values.name).trim()) {
      form.setErrors({ name: 'نام دسته‌بندی الزامی است.' });
      return;
    }
    form.setSubmitting(true);
    try {
      await api.knowledge.categories.create({
        name: String(form.values.name).trim(),
        description: String(form.values.description) || null,
      });
      toast.success('دسته‌بندی جدید ایجاد شد.');
      setModalOpen(false);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ایجاد دسته‌بندی ناموفق بود.');
    } finally {
      form.setSubmitting(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await api.knowledge.categories.remove(deleting.id);
      toast.success('دسته‌بندی حذف شد.');
      setDeleting(null);
      await Promise.all([reload(), docsResult.reload()]);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'حذف دسته‌بندی ناموفق بود.');
    } finally {
      setDeleteLoading(false);
    }
  }

  const columns: Column<KnowledgeCategory>[] = [
    { key: 'name', header: 'دسته‌بندی', render: (c) => <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{c.name}</span> },
    { key: 'description', header: 'توضیحات', render: (c) => c.description || <span className="text-slate-400">—</span> },
    {
      key: 'docs',
      header: 'تعداد اسناد',
      render: (c) => fmtNum((docsResult.data?.items || []).filter((d) => d.category_id === c.id).length),
    },
  ];

  return (
    <div>
      <PageHeader
        title="پایگاه دانش"
        description="دسته‌بندی‌های محتوای اختصاصی سازمان — مبنا برای پاسخ‌دهی RAG"
        actions={<Button icon={<Plus className="h-4 w-4" />} onClick={() => setModalOpen(true)}>دسته‌بندی جدید</Button>}
      />

      <DataTable
        columns={columns}
        rows={data?.items || []}
        loading={loading}
        rowKey={(c) => c.id}
        emptyTitle="دسته‌بندی‌ای وجود ندارد"
        emptyDescription="اولین دسته‌بندی پایگاه دانش را ایجاد کنید"
        rowActions={(c) => (
          <button onClick={() => setDeleting(c)} className="rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-500" title="حذف">
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      />

      <div className="mt-6 rounded-2xl border border-blue-200 dark:border-blue-800 bg-blue-500/5 p-4 text-xs leading-6 text-slate-500 dark:text-slate-400">
        <BookOpen className="mb-2 h-4 w-4 text-blue-500" />
        اسناد و محتوای هر دسته‌بندی در صفحه <a href="/admin/documents" className="font-bold text-blue-600 dark:text-blue-400 hover:underline">مدیریت مستندات</a> مدیریت می‌شوند.
        پاسخ‌دهی «فقط پایگاه دانش» و «ترکیبی» بر اساس همین محتوا انجام می‌شود.
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="ایجاد دسته‌بندی جدید"
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)} disabled={form.submitting}>انصراف</Button>
            <Button onClick={submit} loading={form.submitting}>ایجاد دسته‌بندی</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input label="نام دسته‌بندی *" value={String(form.values.name)} onChange={(e) => form.setField('name', e.target.value)} error={form.errors.name} />
          <Textarea label="توضیحات" rows={2} value={String(form.values.description)} onChange={(e) => form.setField('description', e.target.value)} />
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="حذف دسته‌بندی"
        message={`آیا از حذف دسته‌بندی «${deleting?.name}» مطمئن هستید؟`}
        confirmLabel="حذف"
        danger
        loading={deleteLoading}
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}