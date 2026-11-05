import { useState } from 'react';
import { api } from '../lib/api';
import Icon from './Icon';

// The centre's photo from NEA's hawker centre dataset, served through our API (NFR-5).
// Without a photo (or if NEA is unreachable) it shows a placeholder, or nothing when hideIfMissing.
// Give it key={id} where the id can change, so a failed photo doesn't stick to the next centre.
export function CentrePhoto({
  id,
  hasPhoto = true,
  alt = '',
  className = 'size-16',
  hideIfMissing = false,
}: {
  id: number;
  hasPhoto?: boolean;
  alt?: string;
  className?: string;
  hideIfMissing?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  if (!hasPhoto || failed) {
    if (hideIfMissing) return null;
    return (
      <span aria-hidden className={`${className} grid shrink-0 place-items-center rounded-lg bg-stone-100 text-stone-400 dark:bg-stone-800`}>
        <Icon name="pin" className="size-1/2" />
      </span>
    );
  }
  return <img src={api.centrePhotoUrl(id)} alt={alt} loading="lazy" onError={() => setFailed(true)} className={`${className} shrink-0 rounded-lg object-cover`} />;
}
