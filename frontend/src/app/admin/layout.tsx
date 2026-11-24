/**
 * Admin layout — auth guard + theme + toast + RTL shell with right sidebar.
 */
'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AuthProvider, useAuth } from '@/lib/auth-context';
import { ThemeProvider } from '@/lib/theme';
import { ToastProvider } from '@/components/ui/overlays';
import { PageLoader, Button } from '@/components/ui';
import { AdminSidebar, AdminTopbar, useSidebarState } from '@/components/admin/shell';
import { ADMIN_MENU } from '@/lib/constants';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <AdminShell>{children}</AdminShell>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

function AdminShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading, isAdmin } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  // 404-style guard for unknown admin routes → redirect to dashboard
  useEffect(() => {
    if (!pathname.startsWith('/admin')) return;
    const known = ADMIN_MENU.some((m) => pathname.startsWith(m.href)) || pathname === '/admin';
    if (!known) router.replace('/admin/dashboard');
  }, [pathname, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
        <PageLoader label="در حال بررسی دسترسی…" />
      </div>
    );
  }

  // Not logged in → AuthProvider already redirected; belt & suspenders:
  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-900" />
    );
  }

  // Logged in but not an administrator
  if (!isAdmin) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-900 px-4">
        <div className="max-w-md rounded-2xl border border-red-200 dark:border-red-800 bg-white dark:bg-slate-800 p-8 text-center shadow-lg">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-red-500/10 text-2xl">⛔</div>
          <h2 className="text-lg font-extrabold text-slate-800 dark:text-slate-100">دسترسی غیرمجاز</h2>
          <p className="mt-2 text-sm leading-7 text-slate-500 dark:text-slate-400">
            {user.first_name} {user.last_name} عزیز، نقش فعلی شما «{user.role_display_name_fa}» است و به پنل مدیریت دسترسی ندارد.
          </p>
          <div className="mt-5 flex justify-center gap-2">
            <Button variant="outline" onClick={() => router.push('/chat')}>رفتن به محیط چت</Button>
          </div>
        </div>
      </div>
    );
  }

  const currentItem = ADMIN_MENU.filter((m) => pathname.startsWith(m.href)).sort(
    (a, b) => b.href.length - a.href.length
  )[0];

  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-100" dir="rtl">
      <AdminSidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <AdminTopbar title={currentItem?.label || 'پنل مدیریت'} onMobileMenu={() => setMobileOpen(true)} />
        <main className="flex-1 p-4 md:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}