/**
 * Theme state.
 *
 * Three settings, not two: 'system' is the default and is a real, persisted
 * choice — it means "follow the OS", so a user who changes their OS to dark at
 * sunset sees Hakk follow without touching anything. 'light' and 'dark' pin it.
 *
 * The resolved value lands on <html data-theme>, which is the single hook the
 * entire palette hangs off (see src/index.css). Nothing else in the app needs
 * to know the theme exists.
 */

import { useCallback, useEffect, useState } from 'react';

const KEY = 'hakk.theme';
export const THEMES = ['light', 'dark', 'system'];

const query = () => window.matchMedia('(prefers-color-scheme: dark)');

export function readStored() {
  try {
    const v = localStorage.getItem(KEY);
    return THEMES.includes(v) ? v : 'system';
  } catch {
    // Private mode / storage disabled — follow the OS and don't persist.
    return 'system';
  }
}

export function resolve(setting) {
  if (setting === 'system') return query().matches ? 'dark' : 'light';
  return setting;
}

export function apply(setting) {
  const resolved = resolve(setting);
  document.documentElement.setAttribute('data-theme', resolved);
  // Keep the mobile browser chrome in step with the canvas colour.
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', resolved === 'dark' ? '#161815' : '#FAFAF8');
  return resolved;
}

export function useTheme() {
  const [setting, setSetting] = useState(readStored);
  const [resolved, setResolved] = useState(() => resolve(readStored()));

  useEffect(() => {
    setResolved(apply(setting));
    try {
      localStorage.setItem(KEY, setting);
    } catch {
      /* not persistable — the in-memory choice still applies for this session */
    }
  }, [setting]);

  // Only while following the OS does an OS change mean anything.
  useEffect(() => {
    if (setting !== 'system') return;
    const mq = query();
    const onChange = () => setResolved(apply('system'));
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [setting]);

  const cycle = useCallback(
    () => setSetting((s) => THEMES[(THEMES.indexOf(s) + 1) % THEMES.length]),
    [],
  );

  return { setting, resolved, setSetting, cycle };
}
