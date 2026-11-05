import { DISH_PHOTOS } from '../lib/dishPhotos';
import Icon from './Icon';

// Photo of a typical serving of the dish (not a particular stall's), or a bowl placeholder.
// alt is empty because the dish name is always shown next to it.
export function DishThumb({ name, className = 'size-12' }: { name: string; className?: string }) {
  const p = DISH_PHOTOS[name];
  if (!p) {
    return (
      <span aria-hidden className={`${className} grid shrink-0 place-items-center rounded-lg bg-stone-100 text-stone-400 dark:bg-stone-800`}>
        <Icon name="bowl" className="size-1/2" />
      </span>
    );
  }
  return <img src={p.src} alt="" loading="lazy" className={`${className} shrink-0 rounded-lg object-cover`} />;
}

// The attribution each photo's CC licence requires
export function DishPhotoCredit({ name }: { name: string }) {
  const p = DISH_PHOTOS[name];
  if (!p) return null;
  return (
    <p className="text-xs text-stone-500">
      Typical serving, not from a specific stall. Photo:{' '}
      <a href={p.page} target="_blank" rel="noreferrer" className="underline">
        {p.author}
      </a>
      ,{' '}
      {p.licenseUrl ? (
        <a href={p.licenseUrl} target="_blank" rel="noreferrer" className="underline">
          {p.license}
        </a>
      ) : (
        p.license
      )}
      , via Wikimedia Commons
    </p>
  );
}
