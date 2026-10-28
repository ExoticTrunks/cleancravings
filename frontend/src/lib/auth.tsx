// Session handling. With Supabase configured we use Google sign-in (UI prototype, screen 1).
// Without it, a dev sign-in lets the team test logged-in features locally.
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, setTokenGetter, type Me } from './api';

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
const supabase: SupabaseClient | null = url && anon ? createClient(url, anon) : null;
const DEV_KEY = 'cc:dev-token';

function readDevToken(): string | null {
  try {
    return localStorage.getItem(DEV_KEY);
  } catch {
    return null;
  }
}

type AuthState = {
  me: Me | null;
  loading: boolean;
  mode: 'supabase' | 'dev';
  signInWithGoogle: () => Promise<void>;
  devSignIn: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setTokenGetter(async () => {
      if (supabase) return (await supabase.auth.getSession()).data.session?.access_token ?? null;
      return readDevToken();
    });
  }, []);

  const refresh = useCallback(async () => {
    try {
      setMe(await api.me());
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    if (!supabase) return;
    const { data } = supabase.auth.onAuthStateChange(() => refresh());
    return () => data.subscription.unsubscribe();
  }, [refresh]);

  const value = useMemo<AuthState>(
    () => ({
      me,
      loading,
      mode: supabase ? 'supabase' : 'dev',
      refresh,
      signInWithGoogle: async () => {
        if (!supabase) return;
        await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: `${location.origin}/` } });
      },
      devSignIn: async (email: string) => {
        try {
          localStorage.setItem(DEV_KEY, `dev:${email.trim().toLowerCase()}`);
        } catch {
          /* storage blocked */
        }
        await refresh();
      },
      signOut: async () => {
        // UC-0.1 special requirement: clear local session data on sign out
        if (supabase) await supabase.auth.signOut();
        try {
          localStorage.removeItem(DEV_KEY);
        } catch {
          /* ignore */
        }
        setMe(null);
      },
    }),
    [me, loading, refresh],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth outside AuthProvider');
  return v;
}
