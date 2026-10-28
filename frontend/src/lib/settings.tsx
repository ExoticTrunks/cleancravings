// Accessibility settings (UC-10.0): theme and text size, applied instantly, kept on this device.
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export type Theme = 'light' | 'dark' | 'system';
export type TextSize = 'S' | 'M' | 'L' | 'XL';
const SIZES: Record<TextSize, string> = { S: '14px', M: '16px', L: '18px', XL: '20px' };
const KEY = 'cc:settings';

type Settings = { theme: Theme; textSize: TextSize };
type Ctx = Settings & { setTheme: (t: Theme) => void; setTextSize: (s: TextSize) => void; isDark: boolean };

const SettingsCtx = createContext<Ctx | null>(null);

function load(): Settings {
  try {
    return { theme: 'system', textSize: 'M', ...JSON.parse(localStorage.getItem(KEY) || '{}') };
  } catch {
    return { theme: 'system', textSize: 'M' };
  }
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [s, setS] = useState<Settings>(load);
  const [systemDark, setSystemDark] = useState(() => matchMedia('(prefers-color-scheme: dark)').matches);

  useEffect(() => {
    const mq = matchMedia('(prefers-color-scheme: dark)');
    const fn = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  }, []);

  const isDark = s.theme === 'dark' || (s.theme === 'system' && systemDark);
  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark);
    document.documentElement.style.setProperty('--base-size', SIZES[s.textSize]);
    try {
      localStorage.setItem(KEY, JSON.stringify(s));
    } catch {
      /* ignore */
    }
  }, [s, isDark]);

  return (
    <SettingsCtx.Provider
      value={{ ...s, isDark, setTheme: (theme) => setS((p) => ({ ...p, theme })), setTextSize: (textSize) => setS((p) => ({ ...p, textSize })) }}
    >
      {children}
    </SettingsCtx.Provider>
  );
}

export function useSettings(): Ctx {
  const v = useContext(SettingsCtx);
  if (!v) throw new Error('useSettings outside SettingsProvider');
  return v;
}
