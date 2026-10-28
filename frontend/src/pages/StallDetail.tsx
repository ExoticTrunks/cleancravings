// S12 Stall detail + S13 Track record + S15 Log a visit
// (FR-1.5, 1.7, FR-2.1 to 2.4, FR-3.2, FR-4.1, FR-4.4, FR-5.8, NFR-3)
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import BookmarkButton from '../components/BookmarkButton';
import { GradeBadge, HdpBadge, StatusPill } from '../components/badges';
import { ErrorBox, Loading, PageHeader } from '../components/common';
import Icon from '../components/Icon';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { GRADE, fmtDate, hdpCriteria } from '../lib/labels';
import { useApi } from '../lib/useApi';

function LogVisit({ stallId }: { stallId: number }) {
  const { me } = useAuth();
  const nav = useNavigate();
  const dishes = useApi(() => api.dishes(), []);
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [dish, setDish] = useState<number | ''>('');
  const [msg, setMsg] = useState<string | null>(null);

  if (!open)
    return (
      <div>
        {msg && (
          <p role="status" className="card mb-2 border-emerald-300 bg-emerald-50 p-3 text-sm dark:border-emerald-800 dark:bg-emerald-950/30">
            {msg}
          </p>
        )}
        <button className="btn-primary w-full" onClick={() => (me ? (setMsg(null), setOpen(true)) : nav('/signin'))}>
          <Icon name="check" className="size-4" /> Log a visit
        </button>
      </div>
    );

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.addVisit({ stall_id: stallId, rating, note: note || null, dish_type_id: dish === '' ? null : dish });
      setMsg('Visit logged. It’ll nudge your future picks.');
      setOpen(false);
    } catch (err) {
      setMsg((err as Error).message);
    }
  };

  return (
    <form onSubmit={submit} className="card space-y-3 p-4">
      <h3 className="font-semibold">Log a visit</h3>
      <div>
        <span className="mb-1 block text-sm text-stone-500">Rating (optional)</span>
        <div className="flex gap-1" role="radiogroup" aria-label="Rating">
          {[1, 2, 3, 4, 5].map((n) => (
            <button type="button" key={n} role="radio" aria-checked={rating === n} aria-label={`${n} star${n > 1 ? 's' : ''}`} onClick={() => setRating(rating === n ? null : n)}>
              <Icon name="star" filled={!!rating && n <= rating} className={`size-7 ${rating && n <= rating ? 'text-amber-500' : 'text-stone-300'}`} />
            </button>
          ))}
        </div>
      </div>
      <label className="block text-sm">
        <span className="mb-1 block text-stone-500">What did you have? (optional)</span>
        <select className="input" value={dish} onChange={(e) => setDish(e.target.value ? Number(e.target.value) : '')}>
          <option value="">Not sure / not listed</option>
          {dishes.data?.dishes.map((d) => (
            <option key={d.id} value={d.id}>
              {d.dish_name}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-stone-500">Note (optional)</span>
        <textarea className="input" maxLength={300} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        <span className="text-xs text-stone-500">{note.length}/300</span>
      </label>
      <div className="flex gap-2">
        <button className="btn-primary flex-1">Save visit</button>
        <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
      {msg && <p className="text-sm">{msg}</p>}
    </form>
  );
}

export default function StallDetail() {
  const id = Number(useParams().id);
  const { data: s, error, reload } = useApi(() => api.stall(id), [id]);
  const note = useApi(() => api.hdpNote(), []);
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!s) return <Loading />;
  const g = s.safe_grade;
  const tr = s.track_record;
  const criteria = hdpCriteria(s.hdp_category);

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        back
        title={s.stall_name}
        subtitle={
          <>
            <Link to={`/centres/${s.centre.id}`} className="font-medium text-brand-700 hover:underline dark:text-brand-500">
              {s.centre.centre_name}
            </Link>
            {s.unit_number && ` · #${s.unit_number}`}
          </>
        }
        right={<BookmarkButton type="STALL" id={s.id} />}
      />

      {s.centre.status.state !== 'open' && (
        <div className="card mb-4 flex items-center gap-2 border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/30">
          <StatusPill status={s.centre.status} /> {s.centre.status.state === 'closed' ? 'The whole centre is closed, including this stall.' : 'The whole centre will close, including this stall.'}
        </div>
      )}

      {/* NFR-3: grade, track record, closure and healthier tags distinguishable at a glance */}
      <div className="grid gap-4 sm:grid-cols-2">
        <section className="card p-4" aria-labelledby="safe">
          <h2 id="safe" className="mb-3 flex items-center gap-2 font-semibold">
            <Icon name="shield" className="size-5 text-brand-700 dark:text-brand-500" /> SAFE grade
          </h2>
          <div className="flex items-center gap-4">
            <GradeBadge grade={g?.grade_value} underReview={g?.under_review} size="lg" />
            <p className="text-sm text-stone-600 dark:text-stone-300">
              {g ? GRADE[g.grade_value].hint : 'No grade on record from SFA.'}
              {g?.under_review && <span className="block text-amber-700 dark:text-amber-400">Under review by SFA.</span>}
            </p>
          </div>
          <p className="mt-3 text-xs text-stone-500">Source: SFA Track Records{tr.last_updated && `, last updated ${fmtDate(tr.last_updated)}`}.</p>
        </section>

        <section className="card p-4" aria-labelledby="hdp">
          <h2 id="hdp" className="mb-3 flex items-center gap-2 font-semibold">
            <Icon name="leaf" className="size-5 text-lime-700" /> Healthier eating
          </h2>
          {s.hdp_participant ? (
            <>
              <HdpBadge category={s.hdp_category} />
              {criteria.length > 0 && (
                <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Endorsed for">
                  {criteria.map((c) => (
                    <li key={c} className="chip bg-lime-50 text-lime-900 ring-1 ring-lime-200 dark:bg-lime-950/40 dark:text-lime-200 dark:ring-lime-800">
                      {c}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="text-sm text-stone-600 dark:text-stone-300">Not listed in HPB’s Healthier Dining Programme.</p>
          )}
          {/* Unknown (null) shows nothing: most stalls haven't published it, which isn't the same as non-halal */}
          {s.halal === true && <p className="mt-3 text-sm">Halal (per HPB listing)</p>}
          {s.halal === false && <p className="mt-3 text-sm">Non-halal (per HPB listing)</p>}
          {note.data && <p className="mt-3 text-xs text-stone-500">{note.data}</p>}
        </section>
      </div>

      <section className="card mt-4 p-4" id="track-record" aria-labelledby="tr">
        <h2 id="tr" className="mb-3 font-semibold">
          Track record <span className="font-normal text-stone-500">· {tr.observation_window.toLowerCase()}</span>
        </h2>
        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-stone-500">Licence suspended</dt>
            <dd className={`text-lg font-semibold ${tr.suspended_past_year ? 'text-rose-700 dark:text-rose-400' : ''}`}>{tr.suspended_past_year ? 'Yes' : 'No'}</dd>
          </div>
          <div>
            <dt className="text-stone-500">Demerit points</dt>
            <dd className="text-lg font-semibold">{tr.total_demerit_points ?? 'Not published'}</dd>
          </div>
          <div>
            <dt className="text-stone-500">Licensee</dt>
            <dd className="truncate font-medium">{s.licensee_name ?? '—'}</dd>
          </div>
        </dl>
        {tr.grade_history.length > 0 && (
          <>
            <h3 className="mb-2 mt-4 text-sm font-semibold">Grade history</h3>
            <ol className="flex flex-wrap items-center gap-2 text-sm">
              {tr.grade_history.map((h, i) => (
                <li key={h.snapshot_date} className="flex items-center gap-2">
                  {i > 0 && <span className="text-stone-400">←</span>}
                  <GradeBadge grade={h.grade_value} size="sm" />
                  <span className="text-stone-500">since {fmtDate(h.snapshot_date)}</span>
                </li>
              ))}
            </ol>
            <p className="mt-2 text-xs text-stone-500">History starts from when we began saving SFA snapshots.</p>
          </>
        )}
      </section>

      <section className="card mt-4 p-4 text-sm">
        <h2 className="mb-2 font-semibold">Stall info</h2>
        <dl className="grid grid-cols-2 gap-2">
          <dt className="text-stone-500">Cuisine</dt>
          <dd>{s.cuisine ?? 'Not available yet'}</dd>
          <dt className="text-stone-500">Price range</dt>
          <dd>{s.price_range ?? 'Not available yet'}</dd>
          <dt className="text-stone-500">Contact</dt>
          <dd>{s.contact_number ?? 'Not available yet'}</dd>
          <dt className="text-stone-500">Opening hours</dt>
          <dd>{s.operating_hours_available ? '' : 'Not available yet'}</dd>
        </dl>
        <p className="mt-2 text-xs text-stone-500">No official open dataset has these yet. Planned via community reports (UC-9.0).</p>
      </section>

      <div className="mt-4">
        <LogVisit stallId={s.id} />
      </div>
    </div>
  );
}
