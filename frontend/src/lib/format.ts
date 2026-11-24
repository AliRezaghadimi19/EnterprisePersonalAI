/**
 * Formatting helpers — Persian digits, Jalali dates, byte sizes.
 * Wraps lib/jalali.ts; adds date-fns-jalali where richer formatting is needed.
 */
import { toPersianDigits, formatJalaliDate } from './jalali';
import { format as jalaliFormat } from 'date-fns-jalali';

/** Format a number with thousand separators + Persian digits. */
export function fmtNum(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const n = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(n)) return toPersianDigits(value);
  return toPersianDigits(n.toLocaleString('en-US'));
}

/** Jalali date like «۱۵ آبان ۱۴۰۳». */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  try {
    return formatJalaliDate(d);
  } catch {
    return '—';
  }
}

/** Jalali date + time like «۱۵ آبان ۱۴۰۳، ۱۴:۳۰». */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const time = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  return `${fmtDate(iso)}، ${toPersianDigits(time)}`;
}

/** Full Jalali with month name via date-fns-jalali (fallback/detail views). */
export function fmtDateLong(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  try {
    return toPersianDigits(jalaliFormat(d, 'd MMMM yyyy، HH:mm'));
  } catch {
    return fmtDateTime(iso);
  }
}

/** Human-readable byte size with Persian digits. */
export function fmtBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return '—';
  if (bytes < 1024) return `${fmtNum(bytes)} بایت`;
  if (bytes < 1024 * 1024) return `${fmtNum((bytes / 1024).toFixed(1))} کیلوبایت`;
  return `${fmtNum((bytes / (1024 * 1024)).toFixed(1))} مگابایت`;
}

/** Duration in seconds → «۱٫۲ ثانیه». */
export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return '—';
  return `${toPersianDigits(seconds.toFixed(1))} ثانیه`;
}
