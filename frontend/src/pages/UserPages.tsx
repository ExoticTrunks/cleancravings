// S02 Sign in, S03/S10 Preferences, S07 Favourites, S08 Alerts, S09 Profile
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { StatusPill } from '../components/badges';
import { invalidateFavourites } from '../components/BookmarkButton';
import { ErrorBox, Loading, LoginPrompt, PageHeader } from '../components/common';
import Icon from '../components/Icon';
import { api, type ProfileIn, type SafeGrade } from '../lib/api';
import { useAuth } from '../lib/auth';
import { CONDITIONS, PREFERENCES, REASON_LABEL, RESTRICTIONS, THRESHOLDS, fmtDate, fmtDateTime } from '../lib/labels';
import { useSettings, type TextSize, type Theme } from '../lib/settings';
import { useApi } from '../lib/useApi';

export function SignIn() {
  const { mode, signInWithGoogle, devSignIn, me } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState('');
  useEffect(() => {
    if (me) nav(me.has_profile ? '/' : '/setup', { replace: true });
  }, [me, nav]);

  return (
    <div className="mx-auto max-w-md py-8">
      <div className="card p-6 text-center">
        <span className="mx-auto mb-4 grid size-14 place-items-center rounded-2xl bg-brand-700 text-white">
          <Icon name="bowl" className="size-8" />
        </span>
        <h1 className="text-2xl font-bold">Eat well, eat safe</h1>
        <p className="mt-2 text-stone-500">Sign in to save your health profile, bookmarks and visits, and get closure alerts.</p>
        {mode === 'supabase' ? (
          <button className="btn-primary mt-6 w-full" onClick={signInWithGoogle}>
            Continue with Google
          </button>
        ) : (
          <form
            className="mt-6 space-y-2 text-left"
            onSubmit={(e) => {
              e.preventDefault();
              if (email.includes('@')) devSignIn(email);
            }}
          >
            <label className="block text-sm font-medium" htmlFor="email">
              Dev sign-in <span className="font-normal text-stone-500">(Supabase not configured)</span>
            </label>
            <input id="email" className="input" type="email" placeholder="you@e.ntu.edu.sg" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <button className="btn-primary w-full">Sign in</button>
          </form>
        )}
        <Link to="/" className="mt-4 inline-block text-sm text-stone-500 underline">
          Continue as guest
        </Link>
      </div>
    </div>
  );
}

const EMPTY: ProfileIn = { health_conditions: [], dietary_restrictions: [], dietary_preferences: [], budget_min: null, budget_max: null, hygiene_threshold: null, preferred_regions: [] };

export function ProfileEdit({ onboarding = false }: { onboarding?: boolean }) {
  const { me, refresh } = useAuth();
  const nav = useNavigate();
  const regions = useApi(() => api.regions(), []);
  const saved = useApi(() => (me ? api.profile() : Promise.resolve(null)), [me?.id]);
  const [p, setP] = useState<ProfileIn>(EMPTY);
  const [initial, setInitial] = useState<string>(JSON.stringify(EMPTY));
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (saved.data) {
      const { date_last_updated: _, ...rest } = saved.data;
      setP(rest);
      setInitial(JSON.stringify(rest));
    }
  }, [saved.data]);

  if (!me) return <LoginPrompt what="set up your profile" />;
  if (saved.loading) return <Loading />;

  const dirty = JSON.stringify(p) !== initial;
  const flip = <K extends keyof ProfileIn>(k: K, v: string) => {
    const arr = p[k] as string[];
    setP({ ...p, [k]: arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v] });
  };
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.saveProfile(p);
      await refresh();
      nav(onboarding ? '/' : '/profile');
    } catch (e) {
      setErr((e as Error).message); // UC-1.0 EX.1: keep the form as is
    } finally {
      setBusy(false);
    }
  };
  const cancel = () => {
    if (dirty && !confirm('Discard unsaved changes?')) return; // UC-1.0 AC.3
    nav(onboarding ? '/' : '/profile');
  };

  const Box = ({ k, opts }: { k: 'health_conditions' | 'dietary_restrictions' | 'dietary_preferences' | 'preferred_regions'; opts: { value: string; label: string }[] }) => (
    <div className="grid gap-2 sm:grid-cols-2">
      {opts.map((o) => (
        <label key={o.value} className="card flex cursor-pointer items-center gap-3 p-3 has-[:checked]:border-brand-600 has-[:checked]:bg-brand-50 dark:has-[:checked]:bg-brand-900/30">
          <input type="checkbox" className="size-4 accent-brand-700" checked={(p[k] as string[]).includes(o.value)} onChange={() => flip(k, o.value)} />
          {o.label}
        </label>
      ))}
    </div>
  );

  return (
    <form onSubmit={save} className="mx-auto max-w-2xl space-y-6">
      <PageHeader back={!onboarding} title={onboarding ? 'Set up your profile' : 'Edit preferences'} subtitle="All optional. You can change these any time." />
      <fieldset>
        <legend className="mb-2 font-semibold">Health conditions</legend>
        <Box k="health_conditions" opts={CONDITIONS} />
        <p className="mt-2 text-xs text-stone-500">Used only to rate dishes for you. Never shared (NFR-7). General guidance, not medical advice.</p>
      </fieldset>
      <fieldset>
        <legend className="mb-2 font-semibold">Dietary restrictions</legend>
        <Box k="dietary_restrictions" opts={RESTRICTIONS} />
      </fieldset>
      <fieldset>
        <legend className="mb-2 font-semibold">Preferences</legend>
        <Box k="dietary_preferences" opts={PREFERENCES} />
      </fieldset>
      <fieldset>
        <legend className="mb-2 font-semibold">Minimum SAFE grade</legend>
        <div className="flex flex-wrap gap-2">
          {THRESHOLDS.map((t) => (
            <label key={t.label} className="card flex cursor-pointer items-center gap-2 px-3 py-2 has-[:checked]:border-brand-600 has-[:checked]:bg-brand-50 dark:has-[:checked]:bg-brand-900/30">
              <input type="radio" name="th" className="accent-brand-700" checked={p.hygiene_threshold === t.value} onChange={() => setP({ ...p, hygiene_threshold: t.value as SafeGrade | null })} />
              {t.label}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-2 font-semibold">Preferred regions</legend>
        <Box k="preferred_regions" opts={(regions.data ?? []).map((r) => ({ value: r, label: r }))} />
      </fieldset>
      <fieldset>
        <legend className="mb-2 font-semibold">Budget per meal (S$)</legend>
        <div className="flex items-center gap-2">
          <input className="input w-28" type="number" min={0} step={0.5} placeholder="Min" value={p.budget_min ?? ''} onChange={(e) => setP({ ...p, budget_min: e.target.value === '' ? null : Number(e.target.value) })} />
          <span>to</span>
          <input className="input w-28" type="number" min={0} step={0.5} placeholder="Max" value={p.budget_max ?? ''} onChange={(e) => setP({ ...p, budget_max: e.target.value === '' ? null : Number(e.target.value) })} />
        </div>
        <p className="mt-2 text-xs text-stone-500">Saved now, used once stall prices are available.</p>
      </fieldset>
      {err && <ErrorBox message={err} />}
      <div className="sticky bottom-20 flex gap-2 md:bottom-4">
        <button className="btn-primary flex-1" disabled={busy}>
          {busy ? 'Saving…' : 'Save profile'}
        </button>
        <button type="button" className="btn-ghost" onClick={cancel}>
          {onboarding ? 'Skip' : 'Cancel'}
        </button>
      </div>
    </form>
  );
}

export function Saved() {
  const { me } = useAuth();
  const { data, error, loading, reload } = useApi(() => (me ? api.favourites() : Promise.resolve([])), [me?.id]);
  if (!me) return <LoginPrompt what="see your bookmarks" />;
  const groups = [
    { type: 'CENTRE', title: 'Hawker centres', link: (id: number) => `/centres/${id}` },
    { type: 'STALL', title: 'Stalls', link: (id: number) => `/stalls/${id}` },
    { type: 'DISH', title: 'Dishes', link: (_: number) => `/dishes` },
  ] as const;
  const remove = async (id: number) => {
    await api.removeFavourite(id);
    invalidateFavourites();
    reload();
  };
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Saved" subtitle="Bookmarked centres also get closure alerts." />
      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && <Loading />}
      {data?.length === 0 && <p className="text-stone-500">Nothing saved yet. Tap the bookmark icon on a centre, stall or dish.</p>}
      {groups.map((g) => {
        const items = (data ?? []).filter((f) => f.target_type === g.type);
        if (!items.length) return null;
        return (
          <section key={g.type} className="mb-5">
            <h2 className="mb-2 font-semibold">{g.title}</h2>
            <ul className="space-y-2">
              {items.map((f) => (
                <li key={f.id} className="card flex items-center gap-3 p-3">
                  <Link to={f.unavailable ? '#' : g.type === 'DISH' ? `/dishes?focus=${encodeURIComponent(f.label)}` : g.link(f.target_id)} className="min-w-0 flex-1">
                    <p className="truncate font-medium">{f.label}</p>
                    <p className="text-sm text-stone-500">{f.unavailable ? 'Unavailable: no longer in the official list' : f.subtitle}</p>
                  </Link>
                  {f.centre_state && <StatusPill status={{ state: f.centre_state }} />}
                  <button className="rounded-full p-2 text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-800" onClick={() => remove(f.id)} aria-label={`Remove ${f.label}`}>
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

export function Alerts() {
  const { me } = useAuth();
  const { data, error, loading, reload, setData } = useApi(() => (me ? api.alerts() : Promise.resolve([])), [me?.id]);
  if (!me) return <LoginPrompt what="get closure alerts" />;
  const read = async (id: number) => {
    await api.readAlert(id);
    setData((data ?? []).map((a) => (a.id === id ? { ...a, read_status: true } : a)));
  };
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Alerts" subtitle="Closures at hawker centres you’ve saved." />
      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && <Loading />}
      {data?.length === 0 && <p className="text-stone-500">No alerts. Save a hawker centre and we’ll tell you before it closes for cleaning or works.</p>}
      <ul className="space-y-2">
        {data?.map((a) => (
          <li key={a.id} className={`card flex gap-3 p-4 ${a.read_status ? 'opacity-70' : 'border-brand-500'}`}>
            <Icon name="bell" className="mt-0.5 size-5 shrink-0 text-brand-700 dark:text-brand-500" />
            <div className="min-w-0 flex-1">
              <Link to={`/centres/${a.centre_id}`} onClick={() => read(a.id)} className="font-medium hover:underline">
                {a.message}
              </Link>
              <p className="text-xs text-stone-500">
                {REASON_LABEL[a.closure.reason_type]} · {fmtDate(a.closure.start_date)} to {fmtDate(a.closure.end_date)} · sent {fmtDateTime(a.sent_timestamp)}
              </p>
            </div>
            {!a.read_status && (
              <button className="text-sm text-stone-500 underline" onClick={() => read(a.id)}>
                Mark read
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Settings() {
  const { theme, setTheme, textSize, setTextSize } = useSettings();
  return (
    <section className="card p-4">
      <h2 className="mb-3 font-semibold">Accessibility</h2>
      <p className="mb-1 text-sm text-stone-500">Theme</p>
      <div className="mb-4 flex gap-2">
        {(['light', 'dark', 'system'] as Theme[]).map((t) => (
          <button key={t} onClick={() => setTheme(t)} aria-pressed={theme === t} className={`chip border px-3 py-1.5 text-sm ${theme === t ? 'border-brand-700 bg-brand-700 text-white' : 'border-stone-300 dark:border-stone-700'}`}>
            {t === 'system' ? 'Match device' : t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      <p className="mb-1 text-sm text-stone-500">Text size</p>
      <div className="flex gap-2">
        {(['S', 'M', 'L', 'XL'] as TextSize[]).map((s) => (
          <button key={s} onClick={() => setTextSize(s)} aria-pressed={textSize === s} className={`chip border px-3 py-1.5 text-sm ${textSize === s ? 'border-brand-700 bg-brand-700 text-white' : 'border-stone-300 dark:border-stone-700'}`}>
            {{ S: 'Small', M: 'Default', L: 'Large', XL: 'Extra large' }[s]}
          </button>
        ))}
      </div>
    </section>
  );
}

export function Profile() {
  const { me, signOut } = useAuth();
  const profile = useApi(() => (me ? api.profile() : Promise.resolve(null)), [me?.id]);
  const visits = useApi(() => (me ? api.visits() : Promise.resolve([])), [me?.id]);
  const label = (arr: { value: string; label: string }[], v: string[]) => v.map((x) => arr.find((a) => a.value === x)?.label ?? x).join(', ') || 'None';

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageHeader title={me ? me.display_name || me.email || 'Profile' : 'Profile'} subtitle={me?.email} />
      {!me && <LoginPrompt what="save a profile" />}
      {me && (
        <section className="card p-4">
          <div className="mb-3 flex items-center">
            <h2 className="flex-1 font-semibold">Health & preferences</h2>
            <Link to="/profile/edit" className="btn-ghost px-3 py-1.5 text-sm">
              Edit
            </Link>
          </div>
          {profile.data ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-stone-500">Conditions</dt>
              <dd>{label(CONDITIONS, profile.data.health_conditions)}</dd>
              <dt className="text-stone-500">Restrictions</dt>
              <dd>{label(RESTRICTIONS, profile.data.dietary_restrictions)}</dd>
              <dt className="text-stone-500">Preferences</dt>
              <dd>{label(PREFERENCES, profile.data.dietary_preferences)}</dd>
              <dt className="text-stone-500">Min. grade</dt>
              <dd>{THRESHOLDS.find((t) => t.value === profile.data!.hygiene_threshold)?.label}</dd>
              <dt className="text-stone-500">Regions</dt>
              <dd>{profile.data.preferred_regions.join(', ') || 'Any'}</dd>
            </dl>
          ) : (
            <p className="text-sm text-stone-500">No profile yet.</p>
          )}
        </section>
      )}
      {me && (
        <section className="card p-4">
          <h2 className="mb-2 font-semibold">Visit history</h2>
          {visits.data?.length === 0 && <p className="text-sm text-stone-500">Log a visit from any stall page.</p>}
          <ul className="divide-y divide-stone-100 text-sm dark:divide-stone-800">
            {visits.data?.map((v) => (
              <li key={v.id} className="flex items-center gap-2 py-2">
                <Link to={`/stalls/${v.stall_id}`} className="min-w-0 flex-1">
                  <span className="font-medium">{v.stall_name}</span>
                  <span className="block truncate text-stone-500">
                    {v.centre_name}
                    {v.dish_name && ` · ${v.dish_name}`}
                    {v.note && ` · “${v.note}”`}
                  </span>
                </Link>
                {v.rating && <span className="text-amber-600">{'★'.repeat(v.rating)}</span>}
                <span className="text-stone-500">{fmtDate(v.visit_date)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <Settings />
      {me && (
        <button className="btn-ghost w-full" onClick={signOut}>
          Sign out
        </button>
      )}
    </div>
  );
}
