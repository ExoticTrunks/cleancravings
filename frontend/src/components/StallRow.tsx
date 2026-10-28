import { Link } from 'react-router-dom';
import type { StallSummary } from '../lib/api';
import { GradeBadge, HdpBadge } from './badges';
import Icon from './Icon';

export default function StallRow({ stall, sub, extra }: { stall: StallSummary; sub?: string; extra?: React.ReactNode }) {
  return (
    <Link to={`/stalls/${stall.id}`} className="card flex items-center gap-3 p-3 transition hover:border-brand-500">
      <GradeBadge grade={stall.safe_grade?.grade_value} underReview={stall.safe_grade?.under_review} />
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold">{stall.stall_name}</p>
        <p className="truncate text-sm text-stone-500">
          {sub}
          {stall.unit_number && `${sub ? ' · ' : ''}#${stall.unit_number}`}
          {stall.cuisine && ` · ${stall.cuisine}`}
        </p>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {stall.hdp_participant && <HdpBadge category={stall.hdp_category} />}
          {stall.suspended_past_year && <span className="chip bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200">Suspended in past year</span>}
          {extra}
        </div>
      </div>
      <Icon name="chevron" className="size-5 shrink-0 text-stone-400" />
    </Link>
  );
}
