// S05 Search, S06 Search results, S16 Map view (UC-2.0, FR-1.1 to 1.4, FR-2.5)
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { GradeBadge, StatusPill } from '../components/badges';
import { ErrorBox, Loading, LocationBar, PageHeader } from '../components/common';
import Icon from '../components/Icon';
import MapView from '../components/MapView';
import StallRow from '../components/StallRow';
import { api, type CentreSummary, type SafeGrade, type SearchResult } from '../lib/api';
import { THRESHOLDS } from '../lib/labels';
import { useLocationCtx } from '../lib/location';
import { useApi } from '../lib/useApi';

function CentreCard({ c }: { c: CentreSummary }) {
  const graded = c.grades.A + c.grades.B + c.grades.C + c.grades.NEW;
  return (
    <Link to={`/centres/${c.id}`} className="card block p-4 transition hover:border-brand-500">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold leading-snug">{c.centre_name}</h3>
          <p className="truncate text-sm text-stone-500">
            {c.region}
            {c.distance_km != null && ` · ${c.distance_km} km`} · {c.number_of_stalls} stalls
          </p>
        </div>
        <StatusPill status={c.status} />
      </div>
      <div className="mt-3 flex items-center gap-1.5 text-xs">
        {(['A', 'B', 'NEW', 'C'] as SafeGrade[]).map((g) =>
          c.grades[g] ? (
            <span key={g} className="inline-flex items-center gap-1">
              <GradeBadge grade={g} size="sm" />
              <span className="mr-1 text-stone-600 dark:text-stone-400">{c.grades[g]}</span>
            </span>
          ) : null,
        )}
        {graded === 0 && <span className="text-stone-500">No SAFE grades yet</span>}
        {c.hdp_count > 0 && <span className="ml-auto text-lime-800 dark:text-lime-300">{c.hdp_count} Healthier Dining</span>}
      </div>
    </Link>
  );
}

export default function Finder() {
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const { place } = useLocationCtx();
  const [q, setQ] = useState(params.get('q') ?? '');
  const region = params.get('region') ?? '';
  const minGrade = (params.get('grade') as SafeGrade) || null;
  const view = params.get('view') === 'map' ? 'map' : 'list';
  const [radius, setRadius] = useState<number | null>(null);

  const set = (k: string, v: string | null) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v);
    else p.delete(k);
    setParams(p, { replace: true });
  };

  const regions = useApi(() => api.regions(), []);
  const centres = useApi(
    () => api.centres({ region, min_grade: minGrade, lat: place?.lat, lng: place?.lng, radius_km: place ? radius : null }),
    [region, minGrade, place?.lat, place?.lng, radius],
  );

  // Stall + dish search, debounced (FR-1.3)
  const [hits, setHits] = useState<SearchResult | null>(null);
  useEffect(() => {
    const term = q.trim();
    set('q', term || null);
    if (term.length < 2) return setHits(null);
    const t = setTimeout(() => api.search(term).then(setHits).catch(() => setHits(null)), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    const list = centres.data ?? [];
    return term ? list.filter((c) => `${c.centre_name} ${c.street_address ?? ''} ${c.postal_code ?? ''}`.toLowerCase().includes(term)) : list;
  }, [centres.data, q]);

  return (
    <div>
      <PageHeader title="Finder & Map" subtitle="Hawker centres, stalls and dishes. Filter by region and hygiene." />
      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <div className="min-w-0 space-y-3">
          <div className="relative">
            <Icon name="search" className="absolute left-3 top-3 size-5 text-stone-400" />
            <input className="input pl-10" placeholder="Centre, stall, dish or postal code" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-sm">
              <span className="mb-1 block text-stone-500">Region</span>
              <select className="input py-2" value={region} onChange={(e) => set('region', e.target.value || null)}>
                <option value="">All regions</option>
                {regions.data?.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-stone-500">Hygiene</span>
              <select className="input py-2" value={minGrade ?? ''} onChange={(e) => set('grade', e.target.value || null)}>
                {THRESHOLDS.map((t) => (
                  <option key={t.label} value={t.value ?? ''}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <LocationBar />
          {place && (
            <label className="block text-sm">
              <span className="text-stone-500">Within {radius ? `${radius} km` : 'any distance'}</span>
              <input type="range" min={0} max={15} value={radius ?? 0} onChange={(e) => setRadius(Number(e.target.value) || null)} className="w-full accent-brand-700" />
            </label>
          )}
        </div>

        <div className="min-w-0">
          <div className="mb-3 flex items-center gap-2">
            <p className="text-sm text-stone-500">
              {shown.length} hawker centre{shown.length === 1 ? '' : 's'}
            </p>
            <div className="ml-auto inline-flex rounded-xl bg-stone-200 p-1 text-sm dark:bg-stone-800" role="tablist">
              {(['list', 'map'] as const).map((v) => (
                <button key={v} role="tab" aria-selected={view === v} onClick={() => set('view', v === 'map' ? 'map' : null)} className={`flex items-center gap-1 rounded-lg px-3 py-1.5 ${view === v ? 'bg-white shadow-sm dark:bg-stone-900' : ''}`}>
                  <Icon name={v} className="size-4" /> {v === 'list' ? 'List' : 'Map'}
                </button>
              ))}
            </div>
          </div>

          {centres.error && <ErrorBox message={centres.error} onRetry={centres.reload} />}
          {centres.loading && !centres.data && <Loading />}

          {view === 'map' ? (
            <MapView centres={shown} place={place} radiusKm={radius} onSelect={(id) => nav(`/centres/${id}`)} className="h-[65vh]" />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {shown.map((c) => (
                <CentreCard key={c.id} c={c} />
              ))}
              {centres.data && shown.length === 0 && <p className="text-stone-500">No centres match. Try removing a filter.</p>}
            </div>
          )}

          {hits && (hits.stalls.length > 0 || hits.dishes.length > 0) && (
            <div className="mt-6 space-y-3">
              {hits.stalls.length > 0 && <h2 className="font-semibold">Stalls</h2>}
              {hits.stalls.slice(0, 10).map((s) => (
                <StallRow key={s.id} stall={s} sub={s.centre_name} />
              ))}
              {hits.dishes.length > 0 && (
                <>
                  <h2 className="pt-2 font-semibold">Dishes</h2>
                  <div className="flex flex-wrap gap-2">
                    {hits.dishes.map((d) => (
                      <Link key={d} to={`/dishes?focus=${encodeURIComponent(d)}`} className="chip bg-stone-200 py-1 text-sm dark:bg-stone-800">
                        {d}
                      </Link>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
