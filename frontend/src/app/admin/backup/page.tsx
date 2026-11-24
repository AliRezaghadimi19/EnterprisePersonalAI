/**
 * پشتیبان‌گیری — دانلود فایل JSON کامل پایگاه داده (فقط مدیر کل) (PRD §20).
 */
'use client';

import { useEffect, useState } from 'react';
import { Database, Download, ShieldCheck, FileJson } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { Button, Card, Badge } from '@/components/ui';
import { useToast } from '@/components/ui/overlays';
import { api, downloadFile, ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { fmtDateTime, fmtNum } from '@/lib/format';

interface BackupMeta {
  created_at: string;
  table_count: number;
  table_rows: Record<string, number>;
}

export default function BackupPage() {
  const toast = useToast();
  const { isSuperAdmin } = useAuth();
  const [downloading, setDownloading] = useState(false);
  const [tables, setTables] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    // برای نمایش فهرست جداول، یک بک‌آپ بگیریم و meta آن را استخراج کنیم
    (async () => {
      try {
        const res = await apiFetchMeta();
        setTables(res.table_rows || {});
      } catch {
        /* بی‌خیال — لیست جداول نمایش داده نمی‌شود */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function apiFetchMeta(): Promise<BackupMeta> {
    const res = await fetch(
      `${(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1')}/admin/backup`,
      { headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` } }
    );
    if (!res.ok) throw new ApiError('دریافت اطلاعات بک‌آپ ناموفق بود.', res.status);
    const data = await res.json();
    return data.meta as BackupMeta;
  }

  async function download() {
    setDownloading(true);
    try {
      const ts = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      await downloadFile('/admin/backup', `enterprise-ai-backup-${ts}.json`);
      toast.success('فایل پشتیبان با موفقیت دانلود شد.');
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'دانلود پشتیبان ناموفق بود.');
    } finally {
      setDownloading(false);
    }
  }

  const tableEntries = Object.entries(tables || {});

  return (
    <div>
      <PageHeader
        title="پشتیبان‌گیری"
        description="خروجی کامل JSON از تمام جداول پایگاه داده — فقط مدیر کل"
        actions={
          isSuperAdmin ? (
            <Button icon={<Download className="h-4 w-4" />} onClick={download} loading={downloading}>
              دانلود فایل پشتیبان
            </Button>
          ) : (
            <Badge tone="warn">فقط مدیر کل</Badge>
          )
        }
      />

      {!isSuperAdmin && (
        <p className="mb-4 text-xs text-amber-500">دسترسی به عملیات پشتیبان‌گیری منحصر به مدیر کل (super_admin) است.</p>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="درباره پشتیبان‌گیری" className="lg:col-span-1">
          <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
            <div className="flex items-start gap-3">
              <FileJson className="mt-0.5 h-5 w-5 shrink-0 text-blue-500" />
              <p>فایل خروجی شامل <b>تمام جداول</b> پایگاه داده با فرمت JSON و پشتیبانی کامل از فارسی است.</p>
            </div>
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
              <p>این فایل حاوی اطلاعات حساس (هش رمزها، کلیدهای API) است — در محل امن نگهداری کنید.</p>
            </div>
            <div className="flex items-start gap-3">
              <Database className="mt-0.5 h-5 w-5 shrink-0 text-violet-500" />
              <p>پیشنهاد می‌شود پیش از هر تغییر مهم (مهاجرت، ارتقا) یک نسخه پشتیبان تهیه کنید.</p>
            </div>
          </div>
        </Card>

        <Card title="محتوای پایگاه داده" className="lg:col-span-2">
          {!tables ? (
            <p className="py-10 text-center text-sm text-slate-400">
              {isSuperAdmin ? 'در حال بررسی جداول…' : 'برای مشاهده جزئیات جداول، ابتدا با حساب مدیر کل وارد شوید.'}
            </p>
          ) : tableEntries.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">جدولی یافت نشد.</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {tableEntries.map(([name, rows]) => (
                <div
                  key={name}
                  className="flex items-center justify-between rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900/40 px-4 py-3"
                >
                  <span className="font-mono text-xs text-slate-600 dark:text-slate-300" dir="ltr">{name}</span>
                  <Badge tone={rows > 0 ? 'info' : 'neutral'}>{fmtNum(rows)} ردیف</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
