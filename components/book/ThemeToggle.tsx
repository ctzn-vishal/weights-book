'use client';

import { useSyncExternalStore } from 'react';
import { THEME_STORAGE_KEY } from '@/lib/site';
import { MonitorIcon, MoonIcon, SunIcon } from './icons';

type Pref = 'light' | 'dark' | 'system';

const OPTIONS = [
  { value: 'light', label: 'Light theme', Icon: SunIcon },
  { value: 'dark', label: 'Dark theme', Icon: MoonIcon },
  { value: 'system', label: 'Match system theme', Icon: MonitorIcon },
] as const;

const darkQuery = () => window.matchMedia('(prefers-color-scheme: dark)');

function readPref(): Pref {
  const v = document.documentElement.getAttribute('data-theme-pref');
  return v === 'light' || v === 'dark' ? v : 'system';
}

/** Mirrors the inline <head> script (ThemeScript): class, color-scheme, data attribute, storage. */
function applyTheme(pref: Pref) {
  const root = document.documentElement;
  const dark = pref === 'dark' || (pref === 'system' && darkQuery().matches);
  root.classList.toggle('dark', dark);
  root.style.colorScheme = dark ? 'dark' : 'light';
  root.setAttribute('data-theme-pref', pref);
  try {
    if (pref === 'system') localStorage.removeItem(THEME_STORAGE_KEY);
    else localStorage.setItem(THEME_STORAGE_KEY, pref);
  } catch {
    // storage unavailable (private mode): the choice lasts for this page only
  }
}

/** The preference lives on <html>; subscribe to it, and follow the OS while in 'system'. */
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme-pref'] });
  const mq = darkQuery();
  const onSystem = () => {
    if (readPref() === 'system') applyTheme('system');
  };
  mq.addEventListener('change', onSystem);
  return () => {
    observer.disconnect();
    mq.removeEventListener('change', onSystem);
  };
}

/**
 * Light / dark / system. The pressed styling is CSS keyed on
 * html[data-theme-pref], set before paint, so the control never flashes the
 * wrong state; aria-pressed follows once hydrated.
 */
export function ThemeToggle() {
  const pref = useSyncExternalStore(subscribe, readPref, () => null);
  return (
    <div className="bk-theme" role="group" aria-label="Colour theme">
      {OPTIONS.map(({ value, label, Icon }) => (
        <button
          key={value}
          type="button"
          data-value={value}
          aria-label={label}
          title={label}
          aria-pressed={pref === null ? undefined : pref === value}
          onClick={() => applyTheme(value)}
        >
          <Icon />
        </button>
      ))}
    </div>
  );
}
