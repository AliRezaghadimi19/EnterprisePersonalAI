'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

/**
 * صفحه چت سازمانی — گفتگو با مدل‌های هوش مصنوعی از طریق بک‌اند
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface Message {
  id: string;
  sender_role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

interface Conversation {
  id: string;
  title: string;
  is_pinned?: number | boolean;
  updated_at: string;
}

export default function ChatPage() {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [user, setUser] = useState<{ first_name?: string; last_name?: string; username?: string } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  function authHeaders(): HeadersInit {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
  }

  // بارگیری اطلاعات کاربر و گفتگوها
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.replace('/');
      return;
    }
    (async () => {
      try {
        const me = await fetch(`${API_URL}/auth/me`, { headers: authHeaders() });
        if (me.status === 401) {
          router.replace('/');
          return;
        }
        setUser(await me.json());
        const convs = await fetch(`${API_URL}/chat/conversations`, { headers: authHeaders() });
        if (convs.ok) setConversations(await convs.json());
      } catch {
        /* سرور در دسترس نیست — UI همچنان قابل استفاده می‌ماند */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function openConversation(id: string) {
    setActiveId(id);
    setMessages([]);
    try {
      const res = await fetch(`${API_URL}/chat/conversations/${id}`, { headers: authHeaders() });
      if (res.ok) {
        const detail = await res.json();
        setMessages(detail.messages ?? []);
      }
    } catch { /* ignore */ }
  }

  async function newConversation() {
    try {
      const res = await fetch(`${API_URL}/chat/conversations`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({}),
      });
      if (res.ok) {
        const conv = await res.json();
        setConversations((c) => [conv, ...c]);
        setActiveId(conv.id);
        setMessages([]);
      }
    } catch { /* ignore */ }
  }

  async function send() {
    const content = input.trim();
    if (!content || sending) return;
    setInput('');
    setSending(true);

    // نمایش فوری پیام کاربر
    const localMsg: Message = { id: `local-${Date.now()}`, sender_role: 'user', content, created_at: new Date().toISOString() };
    setMessages((m) => [...m, localMsg]);

    try {
      let convId = activeId;
      if (!convId) {
        const res = await fetch(`${API_URL}/chat/conversations`, {
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({ title: content.slice(0, 40) }),
        });
        if (res.ok) {
          const conv = await res.json();
          convId = conv.id;
          setActiveId(convId);
          setConversations((c) => [conv, ...c]);
        }
      }
      if (!convId) throw new Error('no conversation');

      const res = await fetch(`${API_URL}/chat/conversations/${convId}/messages`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ content }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data?.message) setMessages((m) => [...m, data.message]);
      } else {
        const err = await res.json().catch(() => null);
        setMessages((m) => [
          ...m,
          {
            id: `err-${Date.now()}`,
            sender_role: 'assistant',
            content: err?.detail?.detail_fa || err?.detail || 'خطا در پردازش پیام.',
            created_at: new Date().toISOString(),
          },
        ]);
      }
    } catch {
      setMessages((m) => [
        ...m,
        {
          id: `err-${Date.now()}`,
          sender_role: 'assistant',
          content: 'ارتباط با سرور برقرار نشد. مطمئن شوید سرویس بک‌اند فعال است.',
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    router.replace('/');
  }

  const fullName = user ? `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim() || user.username : '';

  return (
    <main dir="rtl" className="flex h-screen bg-slate-950 text-slate-100">
      {/* نوار کناری — فهرست گفتگوها */}
      <aside className="hidden md:flex w-72 flex-col border-l border-slate-800 bg-slate-900/60">
        <div className="p-4 border-b border-slate-800">
          <h1 className="font-bold text-lg">سامانه هوش مصنوعی سازمانی</h1>
          {fullName && <p className="text-sm text-slate-400 mt-1">{fullName} عزیز، خوش آمدید</p>}
        </div>
        <button
          onClick={newConversation}
          className="m-4 rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2.5 font-medium transition"
        >
          + گفتگوی جدید
        </button>
        <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => openConversation(c.id)}
              className={`w-full text-right rounded-xl px-3 py-2.5 text-sm truncate transition ${
                activeId === c.id ? 'bg-blue-600/20 text-blue-200' : 'hover:bg-slate-800 text-slate-300'
              }`}
            >
              {c.title}
            </button>
          ))}
          {conversations.length === 0 && (
            <p className="text-xs text-slate-500 px-3 py-2">هنوز گفتگویی ندارید.</p>
          )}
        </div>
        <button
          onClick={logout}
          className="m-4 rounded-xl border border-slate-700 hover:bg-slate-800 px-4 py-2.5 text-sm text-slate-300 transition"
        >
          خروج از حساب
        </button>
      </aside>

      {/* ناحیه گفتگو */}
      <section className="flex-1 flex flex-col">
        <header className="md:hidden flex items-center justify-between p-4 border-b border-slate-800">
          <span className="font-bold">هوش مصنوعی سازمانی</span>
          <button onClick={logout} className="text-sm text-slate-400">خروج</button>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center text-slate-500">
              <p className="text-4xl mb-3">💬</p>
              <p>اولین پیام خود را بنویسید تا گفتگو آغاز شود.</p>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.sender_role === 'user' ? 'justify-start' : 'justify-end'}`}>
              <div
                className={`max-w-[85%] md:max-w-[70%] rounded-2xl px-4 py-3 whitespace-pre-wrap leading-7 ${
                  m.sender_role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-md'
                    : 'bg-slate-800 text-slate-100 rounded-bl-md'
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-end">
              <div className="bg-slate-800 rounded-2xl rounded-bl-md px-4 py-3 text-slate-400">
                در حال نوشتن...
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-slate-800 p-4">
          <form
            onSubmit={(e) => { e.preventDefault(); send(); }}
            className="flex gap-3 max-w-3xl mx-auto"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="پیام خود را بنویسید..."
              disabled={sending}
              className="flex-1 rounded-xl bg-slate-800/80 border border-slate-700 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-slate-500 disabled:opacity-60 transition"
            />
            <button
              type="submit"
              disabled={sending || !input.trim()}
              className="rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-6 font-medium transition"
            >
              ارسال
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}