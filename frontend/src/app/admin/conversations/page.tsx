/**
 * مکالمات کاربران — مشاهده همه مکالمات + جزئیات (PRD §15).
 */
'use client';

import { useEffect, useState } from 'react';
import { Bot, Eye, MessagesSquare, User } from 'lucide-react';
import { PageHeader } from '@/components/admin/shell';
import { DataTable } from '@/components/admin/DataTable';
import type { Column } from '@/components/admin/DataTable';
import { Badge } from '@/components/ui';
import { Modal } from '@/components/ui/overlays';
import { useToast } from '@/components/ui/overlays';
import { api, ApiError } from '@/lib/api';
import { useApiList, useDebounce } from '@/lib/hooks';
import { fmtDateTime, fmtDuration, fmtNum } from '@/lib/format';
import type { AdminConversation, AdminConversationDetail, AdminConversationMessage } from '@/types/admin';

export default function ConversationsPage() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search);
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<AdminConversationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const pageSize = 20;

  const { data, loading } = useApiList<AdminConversation>(
    () => api.admin.conversations({ search: debouncedSearch || undefined, page, page_size: pageSize }),
    [debouncedSearch, page]
  );

  async function openDetail(conv: AdminConversation) {
    setDetailLoading(true);
    try {
      const d = await api.admin.conversationDetail(conv.id);
      setDetail(d);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'دریافت مکالمه ناموفق بود.');
    } finally {
      setDetailLoading(false);
    }
  }

  const columns: Column<AdminConversation>[] = [
    {
      key: 'title',
      header: 'مکالمه',
      render: (c) => (
        <div className="max-w-xs">
          <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{c.title || 'بدون عنوان'}</p>
          {c.last_message_preview && <p className="mt-0.5 truncate text-xs text-slate-400">{c.last_message_preview}</p>}
        </div>
      ),
    },
    {
      key: 'user',
      header: 'کاربر',
      render: (c) => (
        <div>
          <p className="text-sm text-slate-700 dark:text-slate-200">{c.full_name}</p>
          <p className="text-xs text-slate-400" dir="ltr">@{c.username}</p>
        </div>
      ),
    },
    { key: 'messages', header: 'پیام‌ها', render: (c) => <Badge tone="info">{fmtNum(c.messages_count)}</Badge> },
    { key: 'model', header: 'مدل', render: (c) => <span className="text-xs text-slate-400">{c.model_id ? 'مدل سازمانی' : '—'}</span> },
    { key: 'updated', header: 'آخرین فعالیت', render: (c) => <span className="text-xs text-slate-400">{fmtDateTime(c.updated_at)}</span> },
  ];

  return (
    <div>
      <PageHeader title="مکالمات کاربران" description="مشاهده مکالمات همه کاربران — دسترسی مدیریتی ثبت و ممیزی می‌شود" />

      <DataTable
        columns={columns}
        rows={data?.items || []}
        loading={loading}
        rowKey={(c) => c.id}
        page={page}
        pageSize={pageSize}
        total={data?.total}
        onPageChange={(p) => setPage(p)}
        searchValue={search}
        onSearchChange={(v) => {
          setSearch(v);
          setPage(1);
        }}
        searchPlaceholder="جستجو در عنوان یا نام کاربر…"
        emptyTitle="مکالمه‌ای یافت نشد"
        emptyAction={<MessagesSquare className="h-8 w-8" />}
        rowActions={(c) => (
          <button onClick={() => openDetail(c)} disabled={detailLoading} className="rounded-lg p-1.5 text-slate-400 hover:bg-blue-500/10 hover:text-blue-500" title="مشاهده">
            <Eye className="h-4 w-4" />
          </button>
        )}
      />

      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail?.title || 'مکالمه'} size="xl">
        {detail && (
          <div>
            <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl bg-slate-50 dark:bg-slate-900/40 px-4 py-2.5 text-xs text-slate-500 dark:text-slate-400">
              <span>کاربر: <b className="text-slate-700 dark:text-slate-200">{detail.full_name}</b> (@{detail.username})</span>
              <span>•</span>
              <span>{fmtNum(detail.messages.length)} پیام</span>
              <span>•</span>
              <span>ایجاد: {fmtDateTime(detail.created_at)}</span>
            </div>
            <div className="space-y-3">
              {detail.messages.map((m: AdminConversationMessage) => (
                <div
                  key={m.id}
                  className={`flex gap-2.5 ${m.sender_role === 'user' ? 'flex-row' : 'flex-row-reverse'}`}
                >
                  <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                    m.sender_role === 'user' ? 'bg-blue-500/10 text-blue-500' : 'bg-violet-500/10 text-violet-500'
                  }`}>
                    {m.sender_role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </div>
                  <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-7 ${
                    m.sender_role === 'user'
                      ? 'bg-blue-600/10 text-slate-700 dark:text-slate-200'
                      : 'bg-slate-100 dark:bg-slate-700/50 text-slate-700 dark:text-slate-200'
                  }`}>
                    <p className="whitespace-pre-wrap">{m.content}</p>
                    {(m.input_tokens || m.output_tokens) && (
                      <p className="mt-1.5 text-[10px] text-slate-400" dir="ltr">
                        in: {fmtNum(m.input_tokens)} · out: {fmtNum(m.output_tokens)} · {fmtDuration(m.processing_time_sec)}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}