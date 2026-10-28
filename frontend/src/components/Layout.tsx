import { NavLink, Outlet, Link } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useApi } from '../lib/useApi';
import Icon, { type IconName } from './Icon';

const TABS: { to: string; label: string; icon: IconName }[] = [
  { to: '/', label: 'For you', icon: 'home' },
  { to: '/finder', label: 'Finder & Map', icon: 'map' },
  { to: '/dishes', label: 'Dishes', icon: 'bowl' },
  { to: '/saved', label: 'Saved', icon: 'bookmark' },
  { to: '/profile', label: 'Profile', icon: 'user' },
];

function AlertsBell() {
  const { me } = useAuth();
  const { data } = useApi(() => (me ? api.alerts() : Promise.resolve([])), [me?.id]);
  const unread = (data ?? []).filter((a) => !a.read_status).length;
  return (
    <Link to="/alerts" className="relative rounded-full p-2 hover:bg-stone-100 dark:hover:bg-stone-800" aria-label={`Alerts${unread ? `, ${unread} unread` : ''}`}>
      <Icon name="bell" />
      {unread > 0 && <span className="absolute right-1 top-1 grid size-4 place-items-center rounded-full bg-rose-600 text-[10px] font-bold text-white">{unread}</span>}
    </Link>
  );
}

export default function Layout() {
  const { me } = useAuth();
  return (
    <div className="min-h-dvh pb-20 md:pb-0">
      <header className="sticky top-0 z-30 border-b border-stone-200 bg-white/90 backdrop-blur dark:border-stone-800 dark:bg-stone-950/90">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-extrabold tracking-tight">
            <span className="grid size-8 place-items-center rounded-lg bg-brand-700 text-white">
              <Icon name="bowl" className="size-5" />
            </span>
            <span className="text-lg">
              Clean<span className="text-brand-700 dark:text-brand-500">Cravings</span>
            </span>
          </Link>
          <nav className="ml-6 hidden gap-1 md:flex" aria-label="Main">
            {TABS.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.to === '/'}
                className={({ isActive }) => `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-100' : 'text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800'}`}
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {me ? <AlertsBell /> : <Link to="/signin" className="btn-primary px-3 py-1.5 text-sm">Sign in</Link>}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-5">
        <Outlet />
      </main>

      <footer className="mx-auto hidden max-w-6xl px-4 pb-8 text-xs text-stone-500 md:block">
        Hygiene data: SFA. Hawker centres and closures: NEA via data.gov.sg. Healthier Dining: HPB. Maps: OneMap (SLA).
        CleanCravings is an SC2006 student project and isn't affiliated with these agencies.
      </footer>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-stone-200 bg-white pb-[env(safe-area-inset-bottom)] dark:border-stone-800 dark:bg-stone-950 md:hidden" aria-label="Main">
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.to === '/'} className={({ isActive }) => `flex flex-col items-center gap-0.5 py-2 text-[11px] ${isActive ? 'text-brand-700 dark:text-brand-500' : 'text-stone-500'}`}>
            <Icon name={t.icon} className="size-6" />
            {t.label.split(' ')[0]}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
