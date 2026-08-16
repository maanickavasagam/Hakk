import { AlertCircle, Check, Loader2, Mail, Monitor, Moon, Sun, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTheme } from '../lib/theme';

/** Wordmark — a bracket glyph, sage on warm white. Fills come off the powder
 *  scale rather than fixed hexes so the mark sits in either theme instead of
 *  glaring out of a dark sidebar. */
export function Logo({ size = 'md' }) {
  const dim = size === 'sm' ? 28 : size === 'lg' ? 44 : 34;
  const text = size === 'sm' ? 'text-lg' : size === 'lg' ? 'text-3xl' : 'text-2xl';
  return (
    <span className="inline-flex items-center gap-2.5 select-none">
      <svg width={dim} height={dim} viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="9" className="fill-powder-200" />
        <path
          d="M10 9v14M10 16h12M22 9v14"
          className="stroke-powder-900"
          strokeWidth="2.6"
          strokeLinecap="round"
        />
      </svg>
      <span className={`font-display ${text} tracking-tight text-ink`}>Hakk</span>
    </span>
  );
}

const THEME_UI = {
  light: { icon: Sun, label: 'Light' },
  dark: { icon: Moon, label: 'Dark' },
  system: { icon: Monitor, label: 'System' },
};

/** Cycles light -> dark -> system. The label says which setting is active, not
 *  which one is next, so 'System' can be read as a state rather than a verb. */
export function ThemeToggle({ compact = false }) {
  const { setting, resolved, cycle } = useTheme();
  const { icon: Icon, label } = THEME_UI[setting];

  return (
    <button
      onClick={cycle}
      className="inline-flex items-center gap-2 text-xs text-ink-muted hover:text-ink transition-colors"
      title={
        setting === 'system'
          ? `Following your system setting (currently ${resolved}). Click to pin light.`
          : `${label} theme. Click to switch.`
      }
      aria-label={`Theme: ${label}. Change theme.`}
    >
      <Icon className="w-3.5 h-3.5" strokeWidth={1.75} />
      {!compact && <span>{label}</span>}
    </button>
  );
}

export function Spinner({ className = 'w-4 h-4' }) {
  return <Loader2 className={`${className} animate-spin`} aria-hidden="true" />;
}

export function PageLoader({ label = 'Loading' }) {
  return (
    <div className="flex flex-col items-center justify-center py-30 gap-4 animate-fade-in">
      <Spinner className="w-6 h-6 text-powder-500" />
      <p className="text-sm text-ink-muted">{label}</p>
    </div>
  );
}

export function ErrorNote({ children, onDismiss }) {
  if (!children) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-2xl border border-rust-300/60 bg-rust-100/70 px-4 py-3 animate-scale-in"
    >
      <AlertCircle className="w-[18px] h-[18px] text-rust-500 shrink-0 mt-px" strokeWidth={1.75} />
      <p className="text-sm text-rust-700 leading-relaxed flex-1">{children}</p>
      {onDismiss && (
        <button onClick={onDismiss} className="text-rust-500 hover:text-rust-700 transition-colors">
          <X className="w-4 h-4" strokeWidth={1.75} />
        </button>
      )}
    </div>
  );
}

export function Empty({ icon: Icon, title, body, action }) {
  return (
    <div className="flex flex-col items-center text-center py-20 px-8 animate-fade-up">
      {Icon && (
        <div className="w-14 h-14 rounded-2xl bg-powder-100 grid place-items-center mb-5">
          <Icon className="w-6 h-6 text-powder-700" strokeWidth={1.5} />
        </div>
      )}
      <h3 className="text-2xl mb-2">{title}</h3>
      {body && <p className="text-ink-muted max-w-sm leading-relaxed mb-6">{body}</p>}
      {action}
    </div>
  );
}

/** Sector / status pill with the right hue for its meaning. */
export function StatusPill({ status }) {
  const map = {
    intake: ['pill-neutral', 'In intake'],
    unclassified: ['pill-clay', 'Needs review'],
    active: ['pill-green', 'Active'],
    lawyer_handoff: ['pill-rust', 'Lawyer handoff'],
    resolved: ['pill-green', 'Resolved'],
    locked: ['pill-neutral', 'Locked'],
    awaiting_payment: ['pill-clay', 'Unlock to continue'],
    action_needed: ['pill-clay', 'Action needed'],
    paid: ['pill-green', 'Unlocked'],
    awaiting_response: ['pill-green', 'Awaiting response'],
    lapsed: ['pill-rust', 'Deadline lapsed'],
    completed: ['pill-green', 'Completed'],
    pending_review: ['pill-clay', 'Awaiting your review'],
    approved: ['pill-green', 'Approved'],
    superseded: ['pill-neutral', 'Superseded'],
  };
  const [cls, label] = map[status] || ['pill-neutral', status];
  return <span className={cls}>{label}</span>;
}

/** Toast stack. Deliberately quiet: soft lift, gentle slide, auto-dismiss. */
export function Toasts({ toasts, onDismiss }) {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 w-[min(23rem,calc(100vw-3rem))]">
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} onDismiss={() => onDismiss(t.id)} />
      ))}
    </div>
  );
}

function Toast({ toast, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, toast.severity === 'urgent' ? 9000 : 6000);
    return () => clearTimeout(timer);
  }, [onDismiss, toast.severity]);

  const tone =
    toast.severity === 'urgent'
      ? 'border-rust-300/70 bg-rust-100'
      : toast.severity === 'warn'
        ? 'border-clay-300/60 bg-clay-100'
        : 'border-powder-200 bg-powder-50';
  const dot =
    toast.severity === 'urgent'
      ? 'bg-rust-500'
      : toast.severity === 'warn'
        ? 'bg-clay-500'
        : 'bg-powder-500';

  return (
    <div
      className={`rounded-2xl border ${tone} shadow-float px-4 py-3.5 animate-slide-in-right`}
      role="status"
    >
      <div className="flex items-start gap-3">
        <span className={`w-2 h-2 rounded-full ${dot} mt-1.5 shrink-0 animate-pulse-soft`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-ink leading-snug">{toast.title}</p>
          {toast.body && (
            <p className="text-[0.8125rem] text-ink-soft leading-relaxed mt-1">{toast.body}</p>
          )}
          {toast.emailed && (
            <p
              className="flex items-center gap-1.5 text-2xs uppercase tracking-wider text-ink-faint mt-2"
              title="We also emailed you about this"
            >
              <Mail className="w-3 h-3" strokeWidth={1.75} />
              Emailed
            </p>
          )}
        </div>
        <button
          onClick={onDismiss}
          className="text-ink-faint hover:text-ink transition-colors shrink-0"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" strokeWidth={1.75} />
        </button>
      </div>
    </div>
  );
}

/** Inline confirmation flash used after saves. */
export function SavedFlash({ show, label = 'Saved' }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!show) return;
    setVisible(true);
    const t = setTimeout(() => setVisible(false), 2000);
    return () => clearTimeout(t);
  }, [show]);
  if (!visible) return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-powder-700 animate-fade-in">
      <Check className="w-3.5 h-3.5" strokeWidth={2} />
      {label}
    </span>
  );
}

/** Thin-line section heading with a sage rule. */
export function SectionHead({ eyebrow, title, action }) {
  return (
    <div className="flex items-end justify-between gap-6 mb-6">
      <div>
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h2 className="text-title">{title}</h2>
      </div>
      {action}
    </div>
  );
}
