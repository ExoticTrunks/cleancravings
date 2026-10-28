// S04 Home (for you): FR-5.6 recommendations, UC-6.0 teaser
import { Link } from 'react-router-dom';
import { ErrorBox, FreshnessBanner, Loading, LocationBar } from '../components/common';
import { VerdictBadge } from '../components/badges';
import StallRow from '../components/StallRow';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { halalNote } from '../lib/labels';
import { useLocationCtx } from '../lib/location';
import { useApi } from '../lib/useApi';

export default function Home() {
  const { me } = useAuth();
  const { place } = useLocationCtx();
  const recs = useApi(() => api.recommendations(place?.lat, place?.lng), [place?.lat, place?.lng, me?.id]);
  const dishes = useApi(() => api.dishes(), [me?.id]);
  const name = me?.display_name?.split(' ')[0];

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <section className="min-w-0">
        <FreshnessBanner />
        <h1 className="text-2xl font-bold tracking-tight">{name ? `Hi ${name}, here’s where to eat` : 'Clean, nearby hawker picks'}</h1>
        <p className="mb-4 mt-1 text-stone-500 dark:text-stone-400">
          Stalls from open hawker centres, ordered by SAFE grade{place ? ', distance' : ''}
          {recs.data?.used_profile ? ' and your preferences' : ''}.
        </p>

        <LocationBar />

        {me && !me.has_profile && (
          <Link to="/setup" className="card mt-4 flex items-center gap-3 border-brand-500 bg-brand-50 p-4 dark:bg-brand-900/30">
            <span className="flex-1">
              <strong>Set up your health profile</strong>
              <br />
              <span className="text-sm text-stone-600 dark:text-stone-300">Tell us what to look out for and we’ll tailor picks and dish ratings.</span>
            </span>
            <span className="btn-primary px-3 py-1.5 text-sm">Set up</span>
          </Link>
        )}

        {recs.data?.halal_only && (
          <p className="card mt-4 p-3 text-sm text-stone-600 dark:text-stone-300">{halalNote(recs.data.items.length, recs.data.halal_confirmed)}</p>
        )}

        <div className="mt-4 space-y-2">
          {recs.loading && !recs.data && <Loading label="Finding stalls…" />}
          {recs.error && <ErrorBox message={recs.error} onRetry={recs.reload} />}
          {recs.data && recs.data.items.length === 0 && (
            <div className="card p-6 text-center">
              <p className="font-semibold">No matches found.</p>
              <p className="mt-1 text-sm text-stone-500">
                Try another location or relax your hygiene threshold in your profile.
                {recs.data.halal_only && ' Your halal filter only includes stalls with a confirmed halal status, and most haven’t published one yet.'}
              </p>
            </div>
          )}
          {recs.data?.items.map((it) => (
            <StallRow
              key={it.stall.id}
              stall={it.stall}
              sub={it.centre_name}
              extra={it.reasons
                .filter((r) => !r.startsWith('SAFE Grade') && !r.startsWith('Healthier Dining'))
                .map((r) => (
                  <span key={r} className={`chip whitespace-normal ${r.startsWith('Heads up') ? 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200' : 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300'}`}>
                    {r}
                  </span>
                ))}
            />
          ))}
        </div>
        {recs.data && (
          <p className="mt-4 text-xs text-stone-500">
            {recs.data.excluded_closed > 0 && `${recs.data.excluded_closed} stalls hidden because their centre is closed today. `}
            {recs.data.excluded_by_hygiene > 0 && `${recs.data.excluded_by_hygiene} hidden by your hygiene threshold. `}
            {recs.data.excluded_by_halal > 0 && `${recs.data.excluded_by_halal} hidden because their halal status isn’t confirmed. `}
            {recs.data.disclaimer}
          </p>
        )}
      </section>

      <aside className="min-w-0 space-y-4">
        <div className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Dishes for you</h2>
            <Link to="/dishes" className="text-sm font-medium text-brand-700 dark:text-brand-500">
              See all
            </Link>
          </div>
          {dishes.data?.dishes.slice(0, 5).map((d) => (
            <div key={d.id} className="flex items-center justify-between gap-2 border-t border-stone-100 py-2 text-sm first:border-0 dark:border-stone-800">
              <span className="truncate">{d.dish_name}</span>
              <VerdictBadge verdict={d.verdict} />
            </div>
          ))}
          {dishes.data && dishes.data.conditions.length === 0 && (
            <p className="mt-2 text-xs text-stone-500">Rated with general HPB guidance. {me ? 'Add health conditions in your profile' : 'Sign in and add health conditions'} for tailored ratings.</p>
          )}
        </div>
        <div className="card p-4 text-sm text-stone-600 dark:text-stone-400">
          <h2 className="mb-1 font-semibold text-stone-900 dark:text-stone-100">About SAFE grades</h2>
          SFA grades stalls on their food safety track record since Jan 2026. <strong>A</strong>: no major lapse for 3+ years. <strong>B</strong>: 1 to 3 years.{' '}
          <strong>C</strong>: recent major lapse. <strong>NEW</strong>: open under a year, not a failing grade.
        </div>
      </aside>
    </div>
  );
}
