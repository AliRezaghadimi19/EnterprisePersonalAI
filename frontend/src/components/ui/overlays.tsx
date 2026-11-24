/**
 * Modal, ConfirmDialog, EmptyState, StatCard, Toast system.
 */
'use client';

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { clsx } from 'clsx';
import { X, CheckCircle2, AlertCircle, Info, Inbox } from 'lucide-react';
import { Button, Spinner, cn } from './index';

// ---------- Modal -------------------------------------------------------------
interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  children: ReactNode;
  footer?: ReactNode;
}

const modalSizes = { sm: 'max-w-md', md: 'max-w-xl', lg: 'max-w-3xl', xl: 'max-w-5xl' };

export function Modal({ open, onClose, title, size = 'md', children, footer }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose} />
      <div
        className={cn(
          'relative w-full rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-2xl max-h-[90vh] flex flex-col',
          modalSizes[size]
        )}
      >
        <header className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-700">
          <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">{title}</h3>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-slate-600 dark:hover:text-slate-200 transition"
            aria-label="بستن"
          >
            <X className="w-5 h-5" />
          </button>
        </header>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <footer className="flex items-center justify-end gap-2 px-5 py-4 border-t border-slate-100 dark:border-slate-700">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}

// ---------- ConfirmDialog --------------------------------------------------------
interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onClose: () => void;
  danger?: boolean;
  loading?: boolean;
}

export function ConfirmDialog({
  open, title, message, confirmLabel = 'تأیید', onConfirm, onClose, danger, loading,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} onClose={onClose} title={title} size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={loading}>انصراف</Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-slate-600 dark:text-slate-300 leading-7">{message}</p>
    </Modal>
  );
}

// ---------- EmptyState --------------------------------------------------------------
interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-14 text-center">
      <div className="rounded-2xl bg-slate-100 dark:bg-slate-700/50 p-4 text-slate-400">
        <Inbox className="w-8 h-8" />
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</p>
        {description && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{description}</p>}
      </div>
      {action}
    </div>
  );
}

// ---------- StatCard -------------------------------------------------------------------
interface StatCardProps {
  title: string;
  value: string | number;
  icon?: ReactNode;
  hint?: string;
  loading?: boolean;
  tone?: 'blue' | 'emerald' | 'amber' | 'red' | 'violet';
}

const statTones = {
  blue: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  emerald: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  amber: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  red: 'bg-red-500/10 text-red-600 dark:text-red-400',
  violet: 'bg-violet-500/10 text-violet-600 dark:text-violet-400',
};

export function StatCard({ title, value, icon, hint, loading, tone = 'blue' }: StatCardProps) {
  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{title}</p>
          {loading ? (
            <div className="mt-2 h-7 w-16 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-700" />
          ) : (
            <p className="mt-1.5 text-2xl font-extrabold tracking-tight text-slate-800 dark:text-slate-100">{value}</p>
          )}
          {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
        </div>
        {icon && <div className={cn('rounded-xl p-2.5 shrink-0', statTones[tone])}>{icon}</div>}
      </div>
    </div>
  );
}

// ---------- Toast -------------------------------------------------------------------------
type ToastTone = 'success' | 'error' | 'info';

interface ToastItem {
  id: number;
  tone: ToastTone;
  message: string;
}

interface ToastContextValue {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);
let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const push = useCallback((tone: ToastTone, message: string) => {
    const id = ++toastCounter;
    setToasts((prev) => [...prev, { id, tone, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  const value = useCallback<ToastContextValue>(
    {
      success: (m) => push('success', m),
      error: (m) => push('error', m),
      info: (m) => push('info', m),
    },
    [push]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-5 left-1/2 z-[60] flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-4">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={clsx(
              'flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm shadow-lg backdrop-blur animate-[fadeIn_.15s_ease-out]',
              toast.tone === 'success' && 'border-emerald-500/40 bg-emerald-50/95 dark:bg-emerald-950/90 text-emerald-800 dark:text-emerald-200',
              toast.tone === 'error' && 'border-red-500/40 bg-red-50/95 dark:bg-red-950/90 text-red-800 dark:text-red-200',
              toast.tone === 'info' && 'border-blue-500/40 bg-blue-50/95 dark:bg-blue-950/90 text-blue-800 dark:text-blue-200'
            )}
          >
            {toast.tone === 'success' && <CheckCircle2 className="mt-0.5 h-4.5 w-4.5 h-5 w-5 shrink-0" />}
            {toast.tone === 'error' && <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />}
            {toast.tone === 'info' && <Info className="mt-0.5 h-5 w-5 shrink-0" />}
            <span className="leading-6">{toast.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx;
}

// re-export for convenience
export { Spinner };