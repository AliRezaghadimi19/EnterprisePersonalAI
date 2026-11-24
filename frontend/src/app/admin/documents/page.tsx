/**
 * مدیریت مستندات پایگاه دانش — CRUD + فیلتر + جستجوی معنایی (PRD §11).
 */
'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { FileText, Pencil, Plus, Trash2, Upload } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { DataTable } from '@/components/admin/DataTable';
import type { Column } from '@/components/admin/DataTable';
import { Button, Badge, Input, Select, Textarea } from '@/components/ui';
import { ConfirmDialog, Modal, useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList, useDebounce, useFormState } from '@/lib/hooks';
import { fmtDate, fmtNum } from '@/lib/format';
import { STATUS_BADGES } from '@/lib/constants';
import type { KnowledgeCategory, KnowledgeDocument } from '@/types/entities';

interface DocFormValues extends Record<string, unknown> {
  title: string;
  category_id: string;
  document_type: string;
  content_text: string;
}

const emptyForm: DocFormValues = { title: '', category_id: '', document_type: 'FAQ', content_text: '' };

export default function DocumentsPage() {
  const toast = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<KnowledgeDocument | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [categories, setCategories] = useState<KnowledgeCategory[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebounce(searchQuery);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data, loading, reload } = useApiList<KnowledgeDocument>(
    () => api.knowledge.documents.list({ category_id: categoryFilter || undefined }),
    [categoryFilter],
    ['documents']
  );
  const form = useFormState<DocFormValues>(emptyForm);

  // Semantic search results (only while typing)
  const [semanticResults, setSemanticResults] = useState<Array<{ document_id: string; title: string; content: string; score: number }>>([]);
  useEffect(() => {
    if (!debouncedSearch || debouncedSearch.length < 3) {
      setSemanticResults([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await api.knowledge.search({ query: debouncedSearch, top_k: 5 }) as { results?: Array<{ document_id: string; title: string; content: string; score: number }> };
        if (!cancelled) setSemanticResults(res.results || []);
      } catch {
        if (!cancelled) setSemanticResults([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch]);

  useEffect(() => {
    api.knowledge.categories.list().then((c) => setCategories(c.items)).catch(() => undefined);
  }, []);

  function openCreate() {
    setEditingId(null);
    form.reset();
    setModalOpen(true);
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploading(true);
    try {
      await api.admin.upload(file);
      toast.success(`فایل «${file.name}» به‌عنوان سند جدید ایندکس شد.`);
      await reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'آپلود فایل ناموفق بود.');
    } finally {
      setUploading(false);
    }
  }

  function openEdit(doc: KnowledgeDocument) {
    setEditingId(doc.id);
    form.reset({
      title: doc.title,
      category_id: doc.category_id || '',
      document_type: doc.document_type || 'FAQ',
      content_text: doc.content_text || '',
    } as DocFormValues);
    setModalOpen(true);
  }

  async function submit() {
    const errors: Partial<Record<keyof DocFormValues, string>> = {};
    if (!String(form.values.title).trim()) errors.title = 'عنوان الزامی است.';
    if (!String(form.values.content_text).trim()) errors.content_text = 'متن سند الزامی است.';
    if (Object.keys(errors).length) {
      form.setErrors(errors);
      return;
    }
    form.setSubmitting(true);
    try {
      const payload = {
        title: String(form.values.title).trim(),
        category_id: form.values.category_id || null,
        document_type: form.values.document_type,
        content_text: String(form.values.content_text),
      };
      if (editingId) {
        await api.knowledge.documents.update(editingId, payload);
        toast.success('سند بروزرسانی و بازایندکس شد.');
      } else {
        await api.knowledge.documents.create(payload);
        toast.success('سند جدید ایجاد و ایندکس شد.');
      }
      setModalOpen(false);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره سند ناموفق بود.');
    } finally {
      form.setSubmitting(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await api.knowledge.documents.remove(deleting.id);
      toast.success('سند و چانک‌های برداری آن حذف شد.');
      setDeleting(null);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'حذف سند ناموفق بود.');
    } finally {
      setDeleteLoading(false);
    }
  }

  const columns = useMemo<Column<KnowledgeDocument>[]>(() => [
    { key: 'title', header: 'عنوان', render: (d) => <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{d.title}</span> },
    { key: 'category', header: 'دسته', render: (d) => categories.find((c) => c.id === d.category_id)?.name || '—' },
    { key: 'type', header: 'نوع', render: (d) => <Badge tone="neutral">{d.document_type}</Badge> },
    { key: 'status', header: 'وضعیت', render: (d) => <Badge tone={STATUS_BADGES[d.status] || 'neutral'}>{d.status === 'APPROVED' ? 'تأییدشده' : d.status === 'PENDING' ? 'در انتظار' : 'ردشده'}</Badge> },
    { key: 'created', header: 'تاریخ', render: (d) => <span className="text-xs text-slate-400">{fmtDate(d.created_at)}</span> },
  ], [categories]);

  return (
    <div>
      <PageHeader
        title="مدیریت مستندات"
        description="سؤال‌وجواب‌ها و اسناد اختصاصی — به‌صورت خودکار برای جستجوی معنایی ایندکس می‌شوند"
        actions={
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.csv,.json,.html,.htm"
              className="hidden"
              onChange={handleUpload}
            />
            <Button
              variant="outline"
              icon={<Upload className="h-4 w-4" />}
              loading={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              آپلود فایل
            </Button>
            <Button icon={<Plus className="h-4 w-4" />} onClick={openCreate}>سند جدید</Button>
          </>
        }
      />

      <div className="mb-4">
        <Input
          placeholder="جستجوی معنایی در پایگاه دانش (حداقل ۳ حرف)…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {semanticResults.length > 0 && (
          <div className="mt-2 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 p-3">
            <p className="mb-2 text-xs font-bold text-slate-500 dark:text-slate-400">نتایج جستجوی معنایی ({fmtNum(semanticResults.length)}):</p>
            <ul className="space-y-2">
              {semanticResults.map((r, idx) => (
                <li key={idx} className="rounded-xl bg-slate-50 dark:bg-slate-900/40 p-3 text-xs">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-slate-700 dark:text-slate-200">{r.title}</p>
                    <span className="text-slate-400" dir="ltr">score: {r.score?.toFixed(3)}</span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-slate-500 dark:text-slate-400">{r.content}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <DataTable
        columns={columns}
        rows={data?.items || []}
        loading={loading}
        rowKey={(d) => d.id}
        emptyTitle="سندی وجود ندارد"
        emptyDescription="اولین سند پایگاه دانش را ایجاد کنید"
        filters={
          <Select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            options={categories.map((c) => ({ value: c.id, label: c.name }))}
            placeholder="همه دسته‌ها"
            className="!w-44"
          />
        }
        rowActions={(d) => (
          <div className="flex items-center gap-1">
            <button onClick={() => openEdit(d)} className="rounded-lg p-1.5 text-slate-400 hover:bg-blue-500/10 hover:text-blue-500" title="ویرایش">
              <Pencil className="h-4 w-4" />
            </button>
            <button onClick={() => setDeleting(d)} className="rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-500" title="حذف">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        )}
      />

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingId ? 'ویرایش سند' : 'ایجاد سند جدید'}
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)} disabled={form.submitting}>انصراف</Button>
            <Button onClick={submit} loading={form.submitting}>{editingId ? 'ذخیره تغییرات' : 'ایجاد و ایندکس'}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="عنوان *" value={String(form.values.title)} onChange={(e) => form.setField('title', e.target.value)} error={form.errors.title} />
            <Select
              label="دسته‌بندی"
              value={String(form.values.category_id)}
              onChange={(e) => form.setField('category_id', e.target.value)}
              options={categories.map((c) => ({ value: c.id, label: c.name }))}
              placeholder="بدون دسته"
            />
          </div>
          <Select
            label="نوع سند"
            value={String(form.values.document_type)}
            onChange={(e) => form.setField('document_type', e.target.value)}
            options={[
              { value: 'FAQ', label: 'سؤال و جواب' },
              { value: 'TXT', label: 'متن' },
              { value: 'PDF', label: 'PDF' },
              { value: 'DOCX', label: 'Word' },
            ]}
          />
          <Textarea
            label="متن سند *"
            rows={10}
            value={String(form.values.content_text)}
            onChange={(e) => form.setField('content_text', e.target.value)}
            error={form.errors.content_text}
          />
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="حذف سند"
        message={`آیا از حذف سند «${deleting?.title}» مطمئن هستید؟ چانک‌های برداری آن نیز حذف می‌شوند.`}
        confirmLabel="حذف سند"
        danger
        loading={deleteLoading}
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}