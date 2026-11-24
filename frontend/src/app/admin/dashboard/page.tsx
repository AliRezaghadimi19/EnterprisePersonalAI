/**
 * Dashboard placeholder — replaced in Phase 2 with real stats & charts.
 */
'use client';

import { PageHeader } from '@/components/admin/shell';
import { Card } from '@/components/ui';

export default function DashboardPage() {
  return (
    <div>
      <PageHeader title="داشبورد مدیریت" description="نمای کلی وضعیت سامانه" />
      <Card>
        <p className="py-16 text-center text-sm text-slate-400">
          داشبورد در فاز بعدی با آمار واقعی و نمودارها تکمیل می‌شود.
        </p>
      </Card>
    </div>
  );
}