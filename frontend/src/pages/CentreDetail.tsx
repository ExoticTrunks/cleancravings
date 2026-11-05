// S11 Hawker centre detail (FR-1.5, FR-1.6, FR-2.5, FR-3.1, FR-3.2, UC-2.1 AC.3)
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import BookmarkButton from '../components/BookmarkButton';
import { StatusPill } from '../components/badges';
import { CentrePhoto } from '../components/CentrePhoto';
import { ErrorBox, Loading, PageHeader } from '../components/common';
import Icon from '../components/Icon';
import MapView from '../components/MapView';
import StallRow from '../components/StallRow';
import { api, type SafeGrade } from '../lib/api';
import { REASON_LABEL, THRESHOLDS, fmtDate, halalNote } from '../lib/labels';
import { useApi } from '../lib/useApi';

export default function CentreDetail() {
  const id = Number(useParams().id);
  const [minGrade, setMinGrade] = useState<SafeGrade | null>(null);
  const [hdpOnly, setHdpOnly] = useState(false);
  // null until the user touches it, so the backend applies their profile's HALAL restriction
  const [halalOnly, setHalalOnly] = useState<boolean | null>(null);
  const { data: c, error, loading, reload } = useApi(() => api.centre(id, minGrade, halalOnly), [id, minGrade, halalOnly]);
  const note = useApi(() => api.hdpNote(), []);

  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!c) return <Loading />;
  const stalls = hdpOnly ? c.stalls.filter((s) => s.hdp_participant) : c.stalls;

  return (
    <div>
      <PageHeader
        back
        title={c.centre_name}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <StatusPill status={c.status} /> {c.street_address}
          </span>
        }
        right={<BookmarkButton type="CENTRE" id={c.id} />}
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="mr-auto text-lg font-semibold">Stalls ({c.stalls.length})</h2>
            <select className="input w-auto py-1.5 text-sm" value={minGrade ?? ''} onChange={(e) => setMinGrade((e.target.value as SafeGrade) || null)} aria-label="Minimum SAFE grade">
              {THRESHOLDS.map((t) => (
                <option key={t.label} value={t.value ?? ''}>
                  {t.label}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" checked={hdpOnly} onChange={(e) => setHdpOnly(e.target.checked)} className="accent-brand-700" /> Healthier Dining only
            </label>
            <label className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" checked={c.halal_only} onChange={(e) => setHalalOnly(e.target.checked)} className="accent-brand-700" /> Confirmed halal only
            </label>
          </div>
          {c.halal_only && <p className="mb-3 text-sm text-stone-600 dark:text-stone-300">{halalNote(c.stalls.length)}</p>}
          {loading && <Loading />}
          <div className="space-y-2">
            {stalls.map((s) => (
              <StallRow key={s.id} stall={s} />
            ))}
          </div>
          {stalls.length === 0 && !loading && (
            <div className="card p-6 text-center text-stone-500">
              No matches found.
              {c.stalls_hidden_by_threshold > 0 && ` ${c.stalls_hidden_by_threshold} stalls are hidden by the hygiene filter.`}
              {c.stalls_hidden_by_halal > 0 && ` ${c.stalls_hidden_by_halal} more haven’t published a halal status.`}
            </div>
          )}
          {c.stalls_hidden_by_threshold > 0 && stalls.length > 0 && <p className="mt-3 text-sm text-stone-500">{c.stalls_hidden_by_threshold} stalls hidden by the hygiene filter.</p>}
          {note.data && <p className="mt-4 text-xs text-stone-500">{note.data}</p>}
        </section>

        <aside className="min-w-0 space-y-4">
          {/* In the sidebar, NEA's photos (about 600 px wide) show near their real size instead of blurring */}
          {c.photo_url && (
            <figure>
              <CentrePhoto key={c.id} id={c.id} alt={c.centre_name} className="h-48 w-full" hideIfMissing />
              <figcaption className="mt-1 text-xs text-stone-500">Photo: NEA</figcaption>
            </figure>
          )}
          <MapView centres={[c]} place={null} selectedId={c.id} className="h-56" />
          <div className="grid grid-cols-2 gap-2">
            <a className="btn-ghost text-sm" href={`https://www.google.com/maps/dir/?api=1&destination=${c.latitude},${c.longitude}`} target="_blank" rel="noreferrer">
              <Icon name="directions" className="size-4" /> Open in Maps
            </a>
            <a className="btn-ghost text-sm" href={`https://www.onemap.gov.sg/?lat=${c.latitude}&lng=${c.longitude}`} target="_blank" rel="noreferrer">
              <Icon name="map" className="size-4" /> OneMap
            </a>
          </div>
          <div className="card p-4">
            <h2 className="mb-2 font-semibold">Upcoming closures</h2>
            {c.closures.length === 0 && <p className="text-sm text-stone-500">None announced. NEA dates marked TBC aren’t shown until confirmed.</p>}
            <ul className="space-y-2 text-sm">
              {c.closures.map((cl) => (
                <li key={cl.id} className="flex gap-3">
                  <Icon name="clock" className="mt-0.5 size-4 shrink-0 text-stone-400" />
                  <div>
                    <strong>
                      {fmtDate(cl.start_date)}
                      {cl.end_date !== cl.start_date && ` – ${fmtDate(cl.end_date)}`}
                    </strong>{' '}
                    {REASON_LABEL[cl.reason_type]}
                    {cl.quarter && <span className="text-stone-500"> ({cl.quarter})</span>}
                    {cl.remarks && <div className="text-stone-500">{cl.remarks}</div>}
                  </div>
                </li>
              ))}
            </ul>
          </div>
          {c.hdp_outlets_without_stall_match.length > 0 && (
            <div className="card p-4 text-sm">
              <h2 className="mb-1 font-semibold">Also in the Healthier Dining Programme</h2>
              <p className="mb-2 text-stone-500">Listed by HPB at this centre but not matched to a stall here yet.</p>
              <ul className="list-disc pl-5">
                {c.hdp_outlets_without_stall_match.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
