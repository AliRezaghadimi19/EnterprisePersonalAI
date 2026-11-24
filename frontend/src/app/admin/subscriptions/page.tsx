/**
 * مدیریت اشتراک‌ها — نمای پلن‌ها روی گروه‌ها (PRD §12).
 */
'use client';

import { useEffect, useState } from 'react';
import { CreditCard, Pencil } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Button, Card, Badge, Input, Select, Toggle } from '@/components/ui';
import { Modal, useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList, useFormState } from '@/lib/hooks';
import { fmtNum } from '@/lib/format';
import { POLICY_LABELS } from '@/lib/constants';
import type { AdminGroup, AdminModel } from '@/types/entities';

interface PlanFormValues extends Record<string, unknown> {
  name: string;
  description: string;
  default_policy: string;
  daily_question_limit: string;
  monthly_question_limit: string;
  daily_token_limit: string;
  monthly_token_limit: string;
}

const emptyForm: PlanFormValues = {
  name: '', description: '', default_policy: 'HYBRID',
  daily_question_limit: '100', monthly_question_limit: '3000',
  daily_token_limit: '200000', monthly_token_limit: '5000000',
};

export default function SubscriptionsPage() {
  const toast = useToast();
  const [editingGroup, setEditingGroup] = useState<AdminGroup | null>(null);
  const [models, setModels] = useState<AdminModel[]>([]);
  const [saving, setSaving] = useState(false);

  const { data: groups, loading, reload } = useApiList<AdminGroup>(() => api.groups.list(), [], ['groups']);
  const form = useFormState<PlanFormValues>(emptyForm);

  useEffect(() => {
    api.models.list().then((m) => setModels(m.items)).catch(() => undefined);
  }, []);

  function openEdit(group: AdminGroup) {
    setEditingGroup(group);
    form.reset({
      name: group.name,
      description: group.description || '',
      default_policy: group.default_policy || 'HYBRID',
      daily_question_limit: String(group.daily_question_limit ?? ''),
      monthly_question_limit: String(group.monthly_question_limit ?? ''),
      daily_token_limit: String(group.daily_token_limit ?? ''),
      monthly_token_limit: String(group.monthly_token_limit ?? ''),
    } as PlanFormValues);
  }

  async function save() {
    if (!editingGroup) return;
    setSaving(true);
    try {
      await api.groups.update(editingGroup.id, {
        name: String(form.values.name).trim(),
        description: String(form.values.description) || null,
        default_policy: form.values.default_policy,
        daily_question_limit: Number(form.values.daily_question_limit) || 0,
        monthly_question_limit: Number(form.values.monthly_question_limit) || 0,
        daily_token_limit: Number(form.values.daily_token_limit) || 0,
        monthly_token_limit: Number(form.values.monthly_token_limit) || 0,
      });
      toast.success('پلن اشتراک بروزرسانی شد.');
      setEditingGroup(null);
      await reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'ذخیره ناموفق بود.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="مدیریت اشتراک‌ها"
        description="پلن‌های اشتراک بر پایه گروه‌ها — هر گروه یک پلن با سقف‌های مستقل"
      />

      {loading ? (
        <p className="py-20 text-center text-sm text-slate-400">در حال بارگذاری…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(groups?.items || []).map((group) => (
            <Card
              key={group.id}
              title={group.name}
              description={group.description || undefined}
              actions={
                <Button size="sm" variant="outline" icon={<Pencil className="h-3.5 w-3.5" />} onClick={() => openEdit(group)}>
                  ویرایش پلن
                </Button>
              }
            >
              <div className="space-y-2.5 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">سیاست پاسخ‌گویی</span>
                  <Badge tone="info">{POLICY_LABELS[group.default_policy] || group.default_policy}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">سؤال روزانه</span>
                  <span className="font-bold text-slate-700 dark:text-slate-200">{fmtNum(group.daily_question_limit)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">سؤال ماهانه</span>
                  <span className="font-bold text-slate-700 dark:text-slate-200">{fmtNum(group.monthly_question_limit)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">توکن روزانه</span>
                  <span className="text-slate-600 dark:text-slate-300" dir="ltr">{fmtNum(group.daily_token_limit)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">توکن ماهانه</span>
                  <span className="text-slate-600 dark:text-slate-300" dir="ltr">{fmtNum(group.monthly_token_limit)}</span>
                </div>
                <div className="flex items-center justify-between border-t border-slate-100 dark:border-slate-700/60 pt-2.5">
                  <span className="text-xs text-slate-400">اعضای گروه</span>
                  <CreditCard className="h-4 w-4 text-slate-300" />
                  <span className="font-bold text-blue-600 dark:text-blue-400">{fmtNum(group.member_count ?? 0)} کاربر</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={!!editingGroup}
        onClose={() => setEditingGroup(null)}
        title={`ویرایش پلن «${editingGroup?.name || ''}»`}
        footer={
          <>
            <Button variant="outline" onClick={() => setEditingGroup(null)} disabled={saving}>انصراف</Button>
            <Button onClick={save} loading={saving}>ذخیره پلن</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="نام پلن" value={String(form.values.name)} onChange={(e) => form.setField('name', e.target.value)} />
          <Select
            label="سیاست پاسخ‌گویی"
            value={String(form.values.default_policy)}
            onChange={(e) => form.setField('default_policy', e.target.value)}
            options={Object.entries(POLICY_LABELS).map(([value, label]) => ({ value, label }))}
          />
          <div className="sm:col-span-2">
            <Input label="توضیحات" value={String(form.values.description)} onChange={(e) => form.setField('description', e.target.value)} />
          </div>
          <Input label="سقف سؤال روزانه" type="number" dir="ltr" value={String(form.values.daily_question_limit)} onChange={(e) => form.setField('daily_question_limit', e.target.value)} />
          <Input label="سقف سؤال ماهانه" type="number" dir="ltr" value={String(form.values.monthly_question_limit)} onChange={(e) => form.setField('monthly_question_limit', e.target.value)} />
          <Input label="سقف توکن روزانه" type="number" dir="ltr" value={String(form.values.daily_token_limit)} onChange={(e) => form.setField('daily_token_limit', e.target.value)} />
          <Input label="سقف توکن ماهانه" type="number" dir="ltr" value={String(form.values.monthly_token_limit)} onChange={(e) => form.setField('monthly_token_limit', e.target.value)} />
        </div>
      </Modal>
    </div>
  );
}