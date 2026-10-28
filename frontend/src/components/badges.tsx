import type { CentreStatus, SafeGrade, Verdict } from '../lib/api';
import { GRADE, VERDICT, fmtDate } from '../lib/labels';
import Icon from './Icon';

export function GradeBadge({ grade, underReview, size = 'md' }: { grade: SafeGrade | null | undefined; underReview?: boolean; size?: 'sm' | 'md' | 'lg' }) {
  const dims = size === 'lg' ? 'h-14 min-w-14 text-2xl rounded-2xl' : size === 'sm' ? 'h-6 min-w-6 text-xs rounded-md' : 'h-9 min-w-9 text-sm rounded-xl';
  if (!grade) {
    return (
      <span title="No SAFE grade on record" className={`${dims} inline-flex items-center justify-center bg-stone-200 px-1.5 font-semibold text-stone-500 dark:bg-stone-800`}>
        –
      </span>
    );
  }
  const g = GRADE[grade];
  return (
    <span
      title={`SAFE Grade ${g.label}: ${g.hint}${underReview ? ' (under review)' : ''}`}
      aria-label={`SAFE Grade ${g.label}${underReview ? ', under review' : ''}`}
      className={`${dims} relative inline-flex items-center justify-center px-1.5 font-bold ${g.cls}`}
    >
      {g.label}
      {underReview && <span className="absolute -right-1 -top-1 size-2.5 rounded-full bg-amber-400 ring-2 ring-white dark:ring-stone-900" />}
    </span>
  );
}

export function StatusPill({ status }: { status: CentreStatus }) {
  switch (status.state) {
    case 'closed':
      return <span className="chip bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200">Closed · reopens {fmtDate(status.reopens_on!)}</span>;
    case 'closing_soon':
      return (
        <span className="chip bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
          {status.days_to_next === 0 ? 'Closes today' : status.days_to_next === 1 ? 'Closes tomorrow' : `Closes in ${status.days_to_next} days`}
        </span>
      );
    case 'not_operating':
      return <span className="chip bg-stone-200 text-stone-600 dark:bg-stone-800">Not operating</span>;
    default:
      return <span className="chip bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200">Open today</span>;
  }
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const v = VERDICT[verdict];
  return (
    <span className={`chip ${v.cls}`} title={v.hint}>
      {v.label}
    </span>
  );
}

export function HdpBadge({ category }: { category?: string | null }) {
  return (
    <span className="chip bg-lime-100 text-lime-900 dark:bg-lime-900/40 dark:text-lime-200" title={category ? `Healthier Dining Programme: ${category}` : 'Healthier Dining Programme'}>
      <Icon name="leaf" className="size-3.5" /> Healthier Dining
    </span>
  );
}
