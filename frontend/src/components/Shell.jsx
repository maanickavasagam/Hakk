import { useCallback, useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  Bell,
  FilePlus2,
  FolderOpen,
  Gauge,
  LayoutGrid,
  LogOut,
  Mail,
  Scale,
} from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/AuthContext';
import { Logo, ThemeToggle, Toasts } from './ui';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutGrid, end: true },
  { to: '/cases', label: 'My Cases', icon: FolderOpen },
  { to: '/new', label: 'Start New Complaint', icon: FilePlus2 },
  { to: '/lawyers', label: 'Find a Lawyer', icon: Scale, stub: true },
];

export default function Shell() {
  const { user, signOut } = useAuth();
  const location = useLocation();
  const [toasts, setToasts] = useState([]);
  const [banner, setBanner] = useState(null);
  const seen = useRef(new Set());
  const first = useRef(true);

  /** Poll reminders. New ones surface as toasts; the most urgent also pins a banner. */
  const poll = useCallback(async () => {
    try {
      const { notifications } = await api.notifications();
      const fresh = notifications.filter((n) => !seen.current.has(n.id));
      notifications.forEach((n) => seen.current.add(n.id));

      // On first load, don't replay history as toasts — just pin the banner.
      if (!first.current && fresh.length) {
        setToasts((t) => [...t, ...fresh.slice(0, 3)].slice(-4));
      }
      first.current = false;

      const urgent =
        notifications.find((n) => n.severity === 'urgent') ||
        notifications.find((n) => n.severity === 'warn');
      setBanner(urgent || null);
    } catch {
      /* offline or signed out — stay quiet */
    }
  }, []);

  useEffect(() => {
    poll();
    const id = setInterval(poll, 4000);
    return () => clearInterval(id);
  }, [poll]);

  const dismissToast = (id) => setToasts((t) => t.filter((x) => x.id !== id));

  const dismissBanner = async () => {
    if (!banner) return;
    const id = banner.id;
    setBanner(null);
    try {
      await api.markRead(id);
    } catch {
      /* no-op */
    }
  };

  return (
    <div className="min-h-screen flex bg-canvas">
      {/* ---- Sidebar ---- */}
      <aside className="hidden lg:flex w-[17.5rem] shrink-0 flex-col border-r border-line bg-surface-warm">
        <div className="px-8 pt-9 pb-8">
          <Logo />
        </div>

        <nav className="px-5 flex-1 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end, stub }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-2xl px-4 py-3 text-[0.9375rem] transition-all duration-180 ease-gentle ${
                  isActive
                    ? 'bg-powder-100 text-powder-900 font-medium'
                    : 'text-ink-soft hover:bg-canvas-sunk hover:text-ink'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={`w-[18px] h-[18px] shrink-0 transition-colors ${
                      isActive ? 'text-powder-700' : 'text-ink-faint group-hover:text-ink-muted'
                    }`}
                    strokeWidth={1.75}
                  />
                  <span className="flex-1">{label}</span>
                  {stub && (
                    <span className="text-2xs uppercase tracking-wider text-ink-faint">Soon</span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="p-5">
          <div className="panel p-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-9 h-9 rounded-full bg-powder-200 grid place-items-center font-display text-powder-900 text-sm shrink-0">
                {(user?.full_name || user?.phone || '?').charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink truncate">
                  {user?.full_name || 'Your account'}
                </p>
                <p className="text-xs text-ink-faint truncate">{user?.phone}</p>
              </div>
            </div>
            <button onClick={signOut} className="btn-quiet w-full justify-start !px-2">
              <LogOut className="w-4 h-4" strokeWidth={1.75} />
              Sign out
            </button>
          </div>
        </div>
      </aside>

      {/* ---- Main column ---- */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Desktop top bar — theme + sign out visible on every page, no scrolling needed */}
        <header className="hidden lg:flex sticky top-0 z-30 items-center justify-end gap-5 px-8 py-4 bg-canvas/85 backdrop-blur-md border-b border-line-soft">
          <ThemeToggle />
          <button onClick={signOut} className="btn-quiet !px-3">
            <LogOut className="w-4 h-4" strokeWidth={1.75} />
            Sign out
          </button>
        </header>

        {/* Mobile nav */}
        <header className="lg:hidden sticky top-0 z-30 bg-canvas/85 backdrop-blur-md border-b border-line">
          <div className="flex items-center justify-between px-5 py-4">
            <Logo size="sm" />
            <div className="flex items-center gap-3">
              <ThemeToggle compact />
              <button onClick={signOut} className="btn-quiet">
                <LogOut className="w-4 h-4" strokeWidth={1.75} />
              </button>
            </div>
          </div>
          <nav className="flex gap-1 px-3 pb-3 overflow-x-auto">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-full px-4 py-2 text-sm whitespace-nowrap transition-colors ${
                    isActive ? 'bg-powder-100 text-powder-900' : 'text-ink-muted'
                  }`
                }
              >
                <Icon className="w-4 h-4" strokeWidth={1.75} />
                {label}
              </NavLink>
            ))}
          </nav>
        </header>

        {/* Reminder banner */}
        {banner && (
          <div
            className={`border-b animate-fade-in ${
              banner.severity === 'urgent'
                ? 'bg-rust-100 border-rust-300/50'
                : 'bg-clay-100 border-clay-300/50'
            }`}
          >
            <div className="max-w-shell mx-auto px-6 sm:px-10 py-3 flex items-center gap-3">
              <Bell
                className={`w-[18px] h-[18px] shrink-0 ${
                  banner.severity === 'urgent' ? 'text-rust-500' : 'text-clay-500'
                }`}
                strokeWidth={1.75}
              />
              <p className="text-sm flex-1 min-w-0">
                <span className="font-semibold text-ink">{banner.title}</span>
                {banner.body && <span className="text-ink-soft"> — {banner.body}</span>}
              </p>
              {banner.emailed && (
                <span
                  className="hidden sm:inline-flex items-center gap-1.5 text-2xs uppercase tracking-wider text-ink-muted shrink-0"
                  title="We also emailed you about this"
                >
                  <Mail className="w-3.5 h-3.5" strokeWidth={1.75} />
                  Emailed
                </span>
              )}
              {banner.case_reference && (
                <NavLink
                  to={`/cases/${banner.case_id}`}
                  className="text-sm font-medium text-ink underline underline-offset-4 decoration-ink-faint hover:decoration-ink shrink-0"
                >
                  Open case
                </NavLink>
              )}
              <button
                onClick={dismissBanner}
                className="text-2xs uppercase tracking-wider text-ink-muted hover:text-ink shrink-0"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        <main key={location.pathname} className="flex-1 animate-fade-in">
          <Outlet />
        </main>

        <footer className="border-t border-line-soft mt-auto">
          <div className="max-w-shell mx-auto px-6 sm:px-10 py-6 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-ink-faint">
              Hakk prepares and tracks consumer complaints. It is not a law firm and does not
              provide legal advice.
            </p>
            <div className="flex items-center gap-5">
              <ThemeToggle />
              <DemoClockBadge />
            </div>
          </div>
        </footer>
      </div>

      <Toasts toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

/** Surfaces the compressed demo timescale, and lets you change it live. */
function DemoClockBadge() {
  const [clock, setClock] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.config().then((c) => setClock(c.demo_clock)).catch(() => {});
  }, []);

  const apply = async (sec) => {
    try {
      setClock(await api.setClock(sec));
      setOpen(false);
    } catch {
      /* no-op */
    }
  };

  if (!clock) return null;
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 text-xs text-ink-muted hover:text-ink transition-colors"
      >
        <Gauge className="w-3.5 h-3.5" strokeWidth={1.75} />
        Demo clock: {clock.description}
      </button>
      {open && (
        <div className="absolute bottom-full right-0 mb-2 card p-2 shadow-float w-56 animate-scale-in">
          <p className="px-3 py-2 text-2xs uppercase tracking-wider text-ink-faint">
            1 statutory day equals
          </p>
          {[
            [0.5, '0.5s — very fast'],
            [2, '2s — demo default'],
            [10, '10s — slow'],
            [86400, 'real time'],
          ].map(([v, label]) => (
            <button
              key={v}
              onClick={() => apply(v)}
              className="w-full text-left px-3 py-2 rounded-xl text-sm text-ink-soft hover:bg-powder-50 hover:text-powder-900 transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
