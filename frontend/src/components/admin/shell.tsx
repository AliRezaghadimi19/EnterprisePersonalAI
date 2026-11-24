/**
 * Admin shell components — RTL sidebar (right), topbar with theme toggle & user chip.
 */
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { Menu, Moon, LogOut, Sun, X } from 'lucide-react';
import { ADMIN_MENU } from '@/lib/constants';
import { useAuth } from '@/lib/auth-context';
import { useTheme } from '@/lib/theme';
import { cn } from '@/components/ui';

export function AdminSidebar({ mobileOpen, onMobileClose }: { mobileOpen: boolean; onMobileClose: () => void }) {
  const pathname = usePathname();
  const { isSuperAdmin } = useAuth();

  const items = ADMIN_MENU.filter((item) => !item.superAdminOnly || isSuperAdmin);

  const nav = (
    <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
      {items.map((item) => {
        const active = pathname.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onMobileClose}
            className={cn(
              'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors',
              active
                ? 'bg-blue-600 text-white shadow-sm font-semibold'
                : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700/60'
            )}
          >
            <Icon className={cn('h-4.5 w-4.5 h-5 w-5 shrink-0', active ? 'text-white' : 'text-slate-400')} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );

  return (
    <>
      {/* Desktop sidebar — first child in RTL flex → sits on the right */}
      <aside className="hidden lg:flex w-72 shrink-0 flex-col border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/40">
        <SidebarHeader />
        {nav}
        <SidebarFooter />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-slate-950/50" onClick={onMobileClose} />
          <aside className="absolute inset-y-0 right-0 flex w-72 flex-col border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-2xl">
            <div className="flex items-center justify-between pl-3">
              <SidebarHeader />
              <button onClick={onMobileClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700" aria-label="بستن منو">
                <X className="h-5 w-5" />
              </button>
            </div>
            {nav}
            <SidebarFooter />
          </aside>
        </div>
      )}
    </>
  );
}

function SidebarHeader() {
  return (
    <div className="flex items-center gap-2.5 px-5 pt-5 pb-2">
      <div className="rounded-xl bg-blue-600 p-2 text-white shadow">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
        </svg>
      </div>
      <div>
        <p className="text-sm font-extrabold text-slate-800 dark:text-slate-100">سامانه هوش مصنوعی</p>
        <p className="text-[11px] text-slate-400">پنل مدیریت سازمانی</p>
      </div>
    </div>
  );
}

function SidebarFooter() {
  const { user } = useAuth();
  return (
    <div className="border-t border-slate-100 dark:border-slate-700 px-4 py-3">
      <Link
        href="/chat"
        className="mb-2 flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 dark:border-slate-600 px-3 py-2 text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/60 transition"
      >
        بازگشت به محیط چت
      </Link>
      <p className="truncate text-center text-[11px] text-slate-400">
        {user ? `${user.first_name} ${user.last_name}` : ''} — {user?.role_display_name_fa || ''}
      </p>
    </div>
  );
}

export function AdminTopbar({ title, onMobileMenu }: { title: string; onMobileMenu: () => void }) {
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-800/60 px-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <button onClick={onMobileMenu} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 lg:hidden" aria-label="باز کردن منو">
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="text-sm font-bold text-slate-700 dark:text-slate-200">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={toggle}
          className="rounded-xl p-2 text-slate-500 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition"
          aria-label={theme === 'dark' ? 'حالت روشن' : 'حالت تاریک'}
        >
          {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>
        {user && (
          <div className="hidden sm:flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-600 px-3 py-1.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600/10 text-xs font-bold text-blue-600 dark:text-blue-400">
              {(user.first_name || user.username || '؟').charAt(0)}
            </div>
            <div className="leading-tight">
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">{user.first_name} {user.last_name}</p>
              <p className="text-[10px] text-slate-400">{user.role_display_name_fa}</p>
            </div>
          </div>
        )}
        <button
          onClick={logout}
          className="rounded-xl p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40 transition"
          aria-label="خروج از حساب"
          title="خروج از حساب"
        >
          <LogOut className="h-5 w-5" />
        </button>
      </div>
    </header>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-xl font-extrabold text-slate-800 dark:text-slate-100">{title}</h2>
        {description && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Sidebar state hook for the layout. */
export function useSidebarState() {
  return useState(false);
}