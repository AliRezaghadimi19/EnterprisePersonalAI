/**
 * مدیریت سهمیه — مصرف مؤثر هر کاربر در برابر سقف‌ها (PRD §13).
 */
'use client';

import { useEffect, useMemo, useState } from 'react';
import { Gauge, Pencil } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { DataTable } from '@/components/admin/DataTable';
import type { Column } from '@/components/admin/DataTable';
import { Button, Badge, Input } from '@/components/ui';
import { Modal, useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList, useDebounce, useFormState } from '@/lib/hooks';
import { fmtNum } from '@/lib/format';
import type { AdminUserListItem } from '@/types/entities';

interface QuotaFormValues extends Record<string, unknown> {
  custom_daily_limit: string;
  custom_monthly_limit: string;
}

const emptyForm: QuotaFormValues = { custom_daily_limit: '', custom_monthly_limit: '' };

export default function QuotasPage() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search);
  const [editingUser, setEditingUser] = useState<AdminUserListItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [usageByUser, setUsageByUser] = useState<Record<string, { questions: number; tokens: number }>>({});

  const { data, loading, reload } = useApiList<AdminUserListItem>(
    () => api.users.list({ search: debouncedSearch || undefined }),
    [debouncedSearch],
    ['users']
  );
  const form = useFormState<QuotaFormValues>(emptyForm);

  // per-user usage for today/month
  useEffect(() => {
    (async () => {
      try {
        const report = await api.admin.usageReport({ group_by: 'user' });
        const map: Record<string, { questions: number; tokens: number }> = {};
        for (const row of report.rows) {
          map[String(row.bucket)] = { questions: Number(row.question_count), tokens: Number(row.total_tokens) };
        }
        setUsageByUser(map);
      } catch { /* non-blocking */ }
    })();
  }, [data]);

  function openEdit(user: AdminUserListItem) {
    setEditingUser(user);
    form.reset({
      custom_daily_limit: user.custom_daily_limit != null ? String(user.custom_daily_limit) : '',
      custom_monthly_limit: user.custom_monthly_limit != null ? String(user.custom_monthly_limit) : '',
    } as QuotaFormValues);
  }

  async function save() {
    if (!editingUser) return;
    setSaving(true);
    try {
      await api.users.update(editingUser.id, {
        custom_daily_limit: form.values.custom_daily_limit ? Number(form.values.custom_daily_limit) : null,
        custom_monthly_limit: form.values.custom_monthly_limit ? Number(form.values.custom_monthly_limit) : null,
      });
      toast.success('سهمیه کاربر بروزرسانی شد.');
      setEditingUser(null);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره سهمیه ناموفق بود.');
    } finally {
      setSaving(false);
    }
  }

  function QuotaBar({ used, limit }: { used: number; limit: number | null | undefined }) {
    const pct = limit && limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
    const tone = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-emerald-500';
    return (
      <div className="min-w-32">
        <div className="flex items-center justify-between text-[11px] text-slate-400">
          <span>{fmtNum(used)}</span>
          <span>از {limit == null ? '∞' : fmtNum(limit)}</span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
          <div className={`h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  }

  const columns = useMemo<Column<AdminUserListItem>[]>(() => [
    {
      key: 'user',
      header: 'کاربر',
      render: (u) => (
        <div>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{u.first_name} {u.last_name}</p>
          <p className="text-xs text-slate-400" dir="ltr">@{u.username}</p>
        </div>
      ),
    },
    { key: 'group', header: 'گروه', render: (u) => <Badge tone="neutral">{u.group_name || '—'}</Badge> },
    { key: 'daily', header: 'سهمیه روزانه', render: (u) => <QuotaBar used={usageByUser[u.id]?.questions ?? 0} limit={u.effective_daily_limit ?? u.custom_daily_limit ?? undefined} /> },
    {
      key: 'override',
      header: 'سقف اختصاصی',
      render: (u) =>
        u.custom_daily_limit != null || u.custom_monthly_limit != null ? (
          <span className="text-xs text-slate-600 dark:text-slate-300" dir="ltr">
            {u.custom_daily_limit != null ? fmtNum(u.custom_daily_limit) : '—'} / {u.custom_monthly_limit != null ? fmtNum(u.custom_monthly_limit) : '—'}
          </span>
        ) : (
          <span className="text-xs text-slate-400">ارث‌بری از گروه</span>
        ),
    },
    {
      key: 'today',
      header: 'مصرف امروز',
      render: (u) => <span className="text-xs text-slate-500 dark:text-slate-400">{fmtNum(usageByUser[u.id]?.questions ?? 0)} سؤال</span>,
    },
  ], [usageByUser]);

  return (
    <div>
      <PageHeader title="مدیریت سهمیه" description="سقف سؤال و توکن هر کاربر — اولویت: اختصاصی > گروه > سامانه" />

      <DataTable
        columns={columns}
        rows={data?.items || []}
        loading={loading}
        rowKey={(u) => u.id}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="جستجوی کاربر…"
        rowActions={(u) => (
          <button onClick={() => openEdit(u)} className="rounded-lg p-1.5 text-slate-400 hover:bg-blue-500/10 hover:text-blue-500" title="ویرایش سهمیه">
            <Pencil className="h-4 w-4" />
          </button>
        )}
      />

      <Modal
        open={!!editingUser}
        onClose={() => setEditingUser(null)}
        title={`سهمیه «${editingUser?.first_name} ${editingUser?.last_name}»`}
        footer={
          <>
            <Button variant="outline" onClick={() => setEditingUser(null)} disabled={saving}>انصراف</Button>
            <Button onClick={save} loading={saving}>ذخیره سهمیه</Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="rounded-xl bg-slate-50 dark:bg-slate-900/40 p-3 text-xs leading-6 text-slate-500 dark:text-slate-400">
            <Gauge className="mb-1 h-4 w-4 text-blue-500" />
            اگر خالی بماند، سقف گروه اعمال می‌شود (گروه «{editingUser?.group_name}»).
          </p>
          <Input
            label="سقف اختصاصی روزانه (سؤال)"
            type="number"
            dir="ltr"
            value={String(form.values.custom_daily_limit)}
            onChange={(e) => form.setField('custom_daily_limit', e.target.value)}
            hint="خالی = ارث‌بری از گروه"
          />
          <Input
            label="سقف اختصاصی ماهانه (سؤال)"
            type="number"
            dir="ltr"
            value={String(form.values.custom_monthly_limit)}
            onChange={(e) => form.setField('custom_monthly_limit', e.target.value)}
            hint="خالی = ارث‌بری از گروه"
          />
        </div>
      </Modal>
    </div>
  );
}