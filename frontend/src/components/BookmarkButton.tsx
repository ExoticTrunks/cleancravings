import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type S } from '../lib/api';
import { useAuth } from '../lib/auth';
import Icon from './Icon';

// Simple module-level cache so every button doesn't refetch the list
let cache: Promise<S['FavouriteOut'][]> | null = null;
export function invalidateFavourites() {
  cache = null;
}

export default function BookmarkButton({ type, id, compact = false }: { type: S['FavouriteTarget']; id: number; compact?: boolean }) {
  const { me } = useAuth();
  const nav = useNavigate();
  const [favId, setFavId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!me) return;
    cache ??= api.favourites();
    cache.then((list) => setFavId(list.find((f) => f.target_type === type && f.target_id === id)?.id ?? null)).catch(() => {});
  }, [me, type, id]);

  const toggle = async () => {
    if (!me) return nav('/signin'); // FR-0.2
    setBusy(true);
    try {
      if (favId) {
        await api.removeFavourite(favId);
        setFavId(null);
        setToast('Removed');
      } else {
        const f = await api.addFavourite(type, id);
        setFavId(f.id);
        setToast(type === 'CENTRE' ? 'Saved. You’ll get closure alerts for it.' : 'Saved to Bookmarks');
      }
      invalidateFavourites();
    } catch (e) {
      setToast((e as Error).message);
    } finally {
      setBusy(false);
      setTimeout(() => setToast(null), 2500);
    }
  };

  return (
    <span className="relative inline-flex">
      <button
        onClick={toggle}
        disabled={busy}
        aria-pressed={!!favId}
        aria-label={favId ? 'Remove bookmark' : 'Bookmark'}
        className={compact ? 'rounded-full p-2 hover:bg-stone-100 dark:hover:bg-stone-800' : 'btn-ghost'}
      >
        <Icon name="bookmark" filled={!!favId} className={`size-5 ${favId ? 'text-brand-700 dark:text-brand-500' : ''}`} />
        {!compact && (favId ? 'Saved' : 'Save')}
      </button>
      {toast && (
        <span role="status" className="absolute right-0 top-full z-20 mt-1 w-max max-w-64 rounded-lg bg-stone-900 px-3 py-1.5 text-xs text-white shadow-lg dark:bg-stone-100 dark:text-stone-900">
          {toast}
        </span>
      )}
    </span>
  );
}
