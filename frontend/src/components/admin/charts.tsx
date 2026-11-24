/**
 * Recharts wrappers — validated 3-slot categorical palette (dataviz skill),
 * Persian-digit ticks, dark-aware. All charts keep one axis, thin marks,
 * hover tooltips by default.
 */
'use client';

import { Area, AreaChart, Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts';
import { toPersianDigits } from '@/lib/jalali';

// Validated categorical slots (light / dark stepped from dataviz reference palette)
export const SERIES_COLORS = {
  light: ['#2a78d6', '#eb6834', '#1baf7a'],
  dark: ['#3987e5', '#d95926', '#199e70'],
};

function useChartTheme() {
  // recharts needs literal colors; read the current mode from html class
  const isDark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
  return {
    isDark,
    colors: isDark ? SERIES_COLORS.dark : SERIES_COLORS.light,
    grid: isDark ? '#334155' : '#e2e8f0',
    text: isDark ? '#94a3b8' : '#64748b',
    tooltipBg: isDark ? '#1e293b' : '#ffffff',
    tooltipBorder: isDark ? '#334155' : '#e2e8f0',
  };
}

const tickStyle = { fontSize: 11 };

function fmtTick(value: string | number): string {
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    // MM-DD slice of an ISO date, in Persian digits
    return toPersianDigits(value.slice(5));
  }
  if (typeof value === 'number') return toPersianDigits(value.toLocaleString('en-US'));
  return toPersianDigits(String(value));
}

interface TooltipEntry {
  name?: string;
  value?: number | string;
}

function VizTooltip({ active, payload, label, formatters }: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  formatters?: Record<string, (v: number) => string>;
}) {
  const { tooltipBg, tooltipBorder } = useChartTheme();
  if (!active || !payload?.length) return null;
  return (
    <div
      dir="rtl"
      className="rounded-xl border px-3 py-2 text-xs shadow-lg"
      style={{ background: tooltipBg, borderColor: tooltipBorder, color: tooltipBorder ? undefined : undefined }}
    >
      {label !== undefined && (
        <p className="mb-1.5 font-semibold text-slate-700 dark:text-slate-200">{fmtTick(label as string | number)}</p>
      )}
      {payload.map((entry, idx) => (
        <p key={idx} className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: (entry as { color?: string }).color }} />
          <span>{entry.name}:</span>
          <span className="font-bold text-slate-800 dark:text-slate-100">
            {formatters && formatters[String(entry.name)]
              ? formatters[String(entry.name)](Number(entry.value))
              : fmtTick(entry.value as string | number)}
          </span>
        </p>
      ))}
    </div>
  );
}

/** Trend of messages/tokens per day — single-series area (no legend needed). */
export function UsageAreaChart({ data, dataKey = 'count', label, color }: {
  data: Array<Record<string, unknown>>;
  dataKey?: string;
  label: string;
  color?: string;
}) {
  const t = useChartTheme();
  const stroke = color || t.colors[0];
  return (
    <div dir="ltr" className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
          <defs>
            <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.25} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={{ ...tickStyle, fill: t.text }} tickFormatter={fmtTick} axisLine={{ stroke: t.grid }} tickLine={false} />
          <YAxis tick={{ ...tickStyle, fill: t.text }} tickFormatter={fmtTick} axisLine={false} tickLine={false} width={44} />
          <Tooltip content={<VizTooltip />} cursor={{ stroke: t.grid }} />
          <Area type="monotone" dataKey={dataKey} name={label} stroke={stroke} strokeWidth={2} fill={`url(#grad-${dataKey})`} dot={false} activeDot={{ r: 4 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Per-model / per-group comparison — horizontal-thin bars, 4px rounded ends. */
export function CategoryBarChart({ data, nameKey, valueKey, label, color }: {
  data: Array<Record<string, unknown>>;
  nameKey: string;
  valueKey: string;
  label: string;
  color?: string;
}) {
  const t = useChartTheme();
  const stroke = color || t.colors[0];
  return (
    <div dir="ltr" className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid stroke={t.grid} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={{ ...tickStyle, fill: t.text }} tickFormatter={fmtTick} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey={nameKey} tick={{ ...tickStyle, fill: t.text }} axisLine={false} tickLine={false} width={140} />
          <Tooltip content={<VizTooltip />} cursor={{ fill: t.grid, fillOpacity: 0.3 }} />
          <Bar dataKey={valueKey} name={label} fill={stroke} radius={[0, 4, 4, 0]} maxBarSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Policy / status distribution — pie with 2px gaps, direct legend. */
export function DistributionPieChart({ data, nameKey, valueKey }: {
  data: Array<Record<string, unknown>>;
  nameKey: string;
  valueKey: string;
}) {
  const t = useChartTheme();
  return (
    <div dir="ltr" className="flex h-64 w-full items-center gap-4">
      <ResponsiveContainer width="55%" height="100%">
        <PieChart>
          <Tooltip content={<VizTooltip />} />
          <Pie data={data} dataKey={valueKey} nameKey={nameKey} innerRadius="55%" outerRadius="85%" paddingAngle={3} stroke="none">
            {data.map((_, idx) => (
              <Cell key={idx} fill={t.colors[idx % t.colors.length]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <ul className="flex-1 space-y-2 text-xs">
        {data.map((row, idx) => (
          <li key={idx} className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: t.colors[idx % t.colors.length] }} />
            <span className="flex-1 truncate">{String(row[nameKey])}</span>
            <span className="font-bold text-slate-800 dark:text-slate-100">{toPersianDigits(String(row[valueKey]))}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}