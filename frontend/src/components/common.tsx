import { useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, type Freshness, type S } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDateTime } from '../lib/labels';
import { useLocationCtx } from '../lib/location';
import { useApi } from '../lib/useApi';
import Icon from './Icon';

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-10 text-stone-500" role="status">
      <span className="size-5 animate-spin rounded-full border-2 border-stone-300 border-t-brand-600" />
      {label}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card my-4 flex items-start gap-3 border-rose-200 bg-rose-50 p-4 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
      <Icon name="info" />
      <div className="flex-1">
        <p>{message}</p>
        {onRetry && (
          <button className="mt-2 font-medium underline" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card px-6 py-10 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mt-2 text-sm text-stone-500">{children}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, back, right }: { title: string; subtitle?: ReactNode; back?: boolean; right?: ReactNode }) {
  const nav = useNavigate();
  return (
    <div className="mb-4 flex items-start gap-3">
      {back && (
        <button onClick={() => nav(-1)} className="mt-0.5 rounded-full p-1.5 hover:bg-stone-200 dark:hover:bg-stone-800" aria-label="Back">
          <Icon name="back" />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <div className="mt-1 text-stone-500 dark:text-stone-400">{subtitle}</div>}
      </div>
      {right}
    </div>
  );
}

/** NFR-2 / NFR-9: last-updated per source, and a clear banner for sample or stale data. */
export function FreshnessBanner() {
  const { data } = useApi<Freshness>(() => api.freshness(), []);
  const [open, setOpen] = useState(false);
  if (!data) return null;
  const stale = data.sources.filter((s) => s.stale && s.source !== 'REF');
  if (!data.any_sample && stale.length === 0 && !open) {
    return (
      <button className="text-xs text-stone-500 underline-offset-2 hover:underline" onClick={() => setOpen(true)}>
        Data sources & last updated
      </button>
    );
  }
  return (
    <div className={`card mb-4 p-3 text-sm ${data.any_sample ? 'border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30' : ''}`}>
      <button className="flex w-full items-center gap-2 text-left font-medium" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Icon name="info" className="size-4 shrink-0" />
        <span className="flex-1">
          {data.any_sample
            ? 'Sample data: some sources are using the bundled demo set, not live government data.'
            : `Offline mode: showing previous data for ${stale.map((s) => s.source).join(', ')}.`}
        </span>
        <Icon name="chevron" className={`size-4 transition ${open ? 'rotate-90' : ''}`} />
      </button>
      {open && (
        <ul className="mt-2 space-y-1 pl-6 text-stone-600 dark:text-stone-400">
          {data.sources.map((s) => (
            <li key={s.source}>
              {s.label}: {s.last_success ? `updated ${fmtDateTime(s.last_success)}` : 'never synced'}
              {s.is_sample && <strong className="text-amber-700 dark:text-amber-400"> (sample)</strong>}
              {s.stale && !s.is_sample && s.source !== 'REF' && <strong className="text-rose-700 dark:text-rose-400"> (stale)</strong>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Pick where you are: GPS or OneMap search (UC-2.0 main flow + AC.1). */
export function LocationBar() {
  const { place, setPlace, locate, locating, error } = useLocationCtx();
  const [q, setQ] = useState('');
  const [results, setResults] = useState<S['GeocodeResult'][] | null>(null);
  const [searchErr, setSearchErr] = useState<string | null>(null);

  const search = async (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim().length < 2) return;
    setSearchErr(null);
    try {
      const r = await api.geocode(q.trim());
      setResults(r);
      if (r.length === 0) setSearchErr('Location not found. Try again.');
    } catch (err) {
      setSearchErr((err as Error).message);
    }
  };

  return (
    <div className="card p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Icon name="pin" className="size-5 text-brand-700 dark:text-brand-500" />
        <span className="font-medium">{place ? place.label : 'No location set'}</span>
        <div className="ml-auto flex flex-wrap gap-2">
          <button className="btn-ghost px-3 py-1.5 text-sm" onClick={locate} disabled={locating}>
            <Icon name="locate" className="size-4" /> {locating ? 'Locating…' : 'Use my location'}
          </button>
          {place && (
            <button className="btn-ghost px-3 py-1.5 text-sm" onClick={() => setPlace(null)}>
              Clear
            </button>
          )}
        </div>
      </div>
      <form onSubmit={search} className="mt-2 flex gap-2">
        <input className="input py-2" placeholder="Or search a place or postal code, e.g. 639798" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search a place" />
        <button className="btn-primary px-3 py-2 text-sm">Go</button>
      </form>
      {(error || searchErr) && <p className="mt-2 text-sm text-rose-700 dark:text-rose-400">{error || searchErr}</p>}
      {results && results.length > 0 && (
        <ul className="mt-2 divide-y divide-stone-200 text-sm dark:divide-stone-800">
          {results.map((r) => (
            <li key={`${r.latitude},${r.longitude},${r.label}`}>
              <button
                className="w-full py-2 text-left hover:text-brand-700"
                onClick={() => {
                  setPlace({ lat: r.latitude, lng: r.longitude, label: r.label });
                  setResults(null);
                  setQ('');
                }}
              >
                {r.label} {r.postal_code && <span className="text-stone-500">· {r.postal_code}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function LoginPrompt({ what }: { what: string }) {
  const { me } = useAuth();
  if (me) return null;
  return (
    <Empty title={`Sign in to ${what}`}>
      <p>Browsing works without an account. Saving things and getting alerts need one.</p>
      <Link to="/signin" className="btn-primary mt-4">
        Sign in
      </Link>
    </Empty>
  );
}
