// Where the user is. GPS first (UC-2.0 step 2-3); if denied, they search a place or
// postal code via OneMap through our backend (UC-2.0 AC.1). Not stored on the server.
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

export type Place = { lat: number; lng: number; label: string };

type Ctx = {
  place: Place | null;
  setPlace: (p: Place | null) => void;
  locate: () => Promise<void>;
  locating: boolean;
  error: string | null;
};

const LocationCtx = createContext<Ctx | null>(null);
const KEY = 'cc:place';

export function LocationProvider({ children }: { children: ReactNode }) {
  const [place, setPlaceState] = useState<Place | null>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(KEY) || 'null');
    } catch {
      return null;
    }
  });
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setPlace = useCallback((p: Place | null) => {
    setPlaceState(p);
    setError(null);
    try {
      sessionStorage.setItem(KEY, JSON.stringify(p));
    } catch {
      /* ignore */
    }
  }, []);

  const locate = useCallback(
    () =>
      new Promise<void>((resolve) => {
        if (!navigator.geolocation) {
          setError('Location isn’t available on this device. Search for a place instead.');
          return resolve();
        }
        setLocating(true);
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            setPlace({ lat: pos.coords.latitude, lng: pos.coords.longitude, label: 'Current location' });
            setLocating(false);
            resolve();
          },
          () => {
            setError('Couldn’t get your location. Search for a place or postal code instead.');
            setLocating(false);
            resolve();
          },
          { timeout: 8000, maximumAge: 60000 },
        );
      }),
    [setPlace],
  );

  return <LocationCtx.Provider value={{ place, setPlace, locate, locating, error }}>{children}</LocationCtx.Provider>;
}

export function useLocationCtx(): Ctx {
  const v = useContext(LocationCtx);
  if (!v) throw new Error('useLocationCtx outside LocationProvider');
  return v;
}
