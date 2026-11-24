/**
 * Shared constants — the 20-item admin menu (PRD §14), label maps.
 */
import type { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard, Users, Building2, ShieldCheck, Globe, Sparkles, Plug, Bot, Scale,
  BookOpen, FileText, CreditCard, Gauge, Paperclip, MessagesSquare, ScrollText,
  BarChart3, LineChart, Settings, DatabaseBackup,
} from 'lucide-react';

export interface AdminMenuItem {
  href: string;
  label: string;
  icon: LucideIcon;
  superAdminOnly?: boolean;
}

export const ADMIN_MENU: AdminMenuItem[] = [
  { href: '/admin/dashboard', label: 'داشبورد', icon: LayoutDashboard },
  { href: '/admin/users', label: 'مدیریت کاربران', icon: Users },
  { href: '/admin/groups', label: 'مدیریت گروه‌ها', icon: Building2 },
  { href: '/admin/roles', label: 'نقش‌ها و دسترسی‌ها', icon: ShieldCheck },
  { href: '/admin/ad-settings', label: 'تنظیمات Active Directory', icon: Globe },
  { href: '/admin/ai', label: 'مدیریت هوش مصنوعی', icon: Sparkles },
  { href: '/admin/providers', label: 'مدیریت Providerها', icon: Plug },
  { href: '/admin/models', label: 'مدیریت مدل‌ها', icon: Bot },
  { href: '/admin/policies', label: 'سیاست پاسخ‌گویی', icon: Scale },
  { href: '/admin/knowledge', label: 'پایگاه دانش', icon: BookOpen },
  { href: '/admin/documents', label: 'مدیریت مستندات', icon: FileText },
  { href: '/admin/subscriptions', label: 'مدیریت اشتراک‌ها', icon: CreditCard },
  { href: '/admin/quotas', label: 'مدیریت سهمیه', icon: Gauge },
  { href: '/admin/file-settings', label: 'تنظیمات فایل‌ها', icon: Paperclip },
  { href: '/admin/conversations', label: 'مکالمات کاربران', icon: MessagesSquare },
  { href: '/admin/request-logs', label: 'لاگ درخواست‌ها', icon: ScrollText },
  { href: '/admin/reports', label: 'گزارش‌های مدیریتی', icon: BarChart3 },
  { href: '/admin/api-usage', label: 'گزارش مصرف API', icon: LineChart },
  { href: '/admin/system-settings', label: 'تنظیمات سامانه', icon: Settings },
  { href: '/admin/backup', label: 'پشتیبان‌گیری', icon: DatabaseBackup, superAdminOnly: true },
];

export const POLICY_LABELS: Record<string, string> = {
  KNOWLEDGE_ONLY: 'فقط پایگاه دانش',
  HYBRID: 'ترکیبی (هوشمند)',
  FREE_AI: 'هوش مصنوعی آزاد',
};

export const ROLE_LABELS: Record<string, string> = {
  super_admin: 'مدیر کل',
  system_admin: 'مدیر سامانه',
  manager_subscriber: 'مشترک مدیریتی',
  tech_subscriber: 'مشترک فنی',
  normal_subscriber: 'مشترک عادی',
};

export const AUTH_TYPE_LABELS: Record<string, string> = {
  LOCAL: 'داخلی',
  ACTIVE_DIRECTORY: 'اکتیو دایرکتوری',
};

export const ACTION_TYPE_LABELS: Record<string, string> = {
  LOGIN_SUCCESS: 'ورود موفق',
  LOGIN_FAILED: 'ورود ناموفق',
  LOGOUT: 'خروج',
  USER_CREATE: 'ایجاد کاربر',
  USER_UPDATE: 'ویرایش کاربر',
  USER_DELETE: 'حذف کاربر',
  GROUP_CREATE: 'ایجاد گروه',
  GROUP_UPDATE: 'ویرایش گروه',
  GROUP_DELETE: 'حذف گروه',
  ROLE_CREATE: 'ایجاد نقش',
  ROLE_UPDATE: 'ویرایش نقش',
  ROLE_DELETE: 'حذف نقش',
  PROVIDER_CREATE: 'ایجاد Provider',
  PROVIDER_UPDATE: 'ویرایش Provider',
  PROVIDER_DELETE: 'حذف Provider',
  MODEL_CREATE: 'ایجاد مدل',
  MODEL_UPDATE: 'ویرایش مدل',
  MODEL_DELETE: 'حذف مدل',
  KNOWLEDGE_CREATE: 'ایجاد محتوای دانش',
  KNOWLEDGE_UPDATE: 'ویرایش محتوای دانش',
  KNOWLEDGE_DELETE: 'حذف محتوای دانش',
  SYSTEM_SETTINGS_UPDATED: 'بروزرسانی تنظیمات سامانه',
  AD_CONFIG_UPDATED: 'بروزرسانی تنظیمات AD',
  CONFIG_CHANGE: 'تغییر پیکربندی',
};

export function actionTypeLabel(action: string): string {
  return ACTION_TYPE_LABELS[action] || action;
}

export const STATUS_BADGES: Record<string, 'success' | 'danger' | 'warn' | 'info' | 'neutral'> = {
  APPROVED: 'success',
  PENDING: 'warn',
  REJECTED: 'danger',
};