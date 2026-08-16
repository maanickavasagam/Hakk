import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowUpRight,
  ClipboardList,
  FileText,
  Gavel,
  Newspaper,
  Radar,
  ShieldCheck,
} from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/AuthContext';
import { PageLoader, StatusPill } from '../components/ui';

const STEPS = [
  {
    icon: ClipboardList,
    title: 'Answer, don’t explain',
    body: 'A short guided set of questions — what happened, who, when, what you want. No free-form chat, no legal vocabulary required.',
  },
  {
    icon: Radar,
    title: 'We place it on the right ladder',
    body: 'Your answers and documents are classified into a sector, which decides which regulator governs your complaint and which statute it cites.',
  },
  {
    icon: FileText,
    title: 'A real complaint, drafted',
    body: 'A formal letter to the correct authority, citing the rule that actually applies — the E-Commerce Rules, the RBI Ombudsman Scheme, TRAI. You review and edit before anything is sent.',
  },
  {
    icon: Gavel,
    title: 'Deadlines that escalate themselves',
    body: 'Every stage has a statutory window. When one lapses without redressal, Hakk drafts the next escalation from your case history and moves you up a rung.',
  },
];

export default function Landing() {
  const { user } = useAuth();
  const [cases, setCases] = useState(null);
  const [articles, setArticles] = useState([]);

  useEffect(() => {
    api.listCases().then((d) => setCases(d.cases)).catch(() => setCases([]));
    api.news().then((d) => setArticles(d.articles)).catch(() => {});
  }, []);

  if (cases === null) return <PageLoader label="Loading your dashboard" />;

  const active = cases.filter((c) => c.status === 'active');
  const needsAttention = cases.filter(
    (c) => c.status === 'lawyer_handoff' || c.status === 'unclassified',
  );
  const firstName = (user?.full_name || '').split(' ')[0];

  return (
    <div className="max-w-shell mx-auto px-6 sm:px-10 py-12 sm:py-16 stagger">
      {/* ---- Header: asymmetric, not a centred hero ---- */}
      <header className="grid lg:grid-cols-[1.4fr_1fr] gap-10 lg:gap-16 items-end mb-16 sm:mb-20">
        <div>
          <p className="eyebrow mb-4">
            {firstName ? `Welcome back, ${firstName}` : 'Welcome back'}
          </p>
          <h1 className="text-display mb-6">
            You have {active.length === 0 ? 'no' : active.length} active{' '}
            {active.length === 1 ? 'case' : 'cases'}
            {active.length > 0 && <span className="text-powder-600">.</span>}
            {active.length === 0 && (
              <span className="block italic text-powder-700">Let’s change that.</span>
            )}
          </h1>
          <p className="lede max-w-prose">
            Hakk holds the deadlines so you don&rsquo;t have to. Start a complaint and the agent
            takes it from a description to a filed, escalating case.
          </p>
        </div>

        <div className="flex flex-col gap-3 lg:items-end">
          <Link to="/new" className="btn-primary">
            <FileText className="w-[18px] h-[18px]" strokeWidth={1.75} />
            Start a new complaint
          </Link>
          {cases.length > 0 && (
            <Link to="/cases" className="btn-ghost">
              View all {cases.length} {cases.length === 1 ? 'case' : 'cases'}
            </Link>
          )}
        </div>
      </header>

      {/* ---- Attention strip ---- */}
      {needsAttention.length > 0 && (
        <section className="mb-16 sm:mb-20">
          <div className="rounded-3xl border border-clay-300/50 bg-clay-100/60 p-6 sm:p-8">
            <p className="eyebrow text-clay-700 mb-4">Needs you</p>
            <div className="space-y-3">
              {needsAttention.map((c) => (
                <Link
                  key={c.id}
                  to={`/cases/${c.id}`}
                  className="flex items-center gap-4 group bg-surface rounded-2xl px-5 py-4 border border-line-soft transition-all duration-180 ease-gentle hover:border-clay-300 hover:shadow-soft"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ink truncate">{c.title}</p>
                    <p className="text-sm text-ink-muted">{c.reference}</p>
                  </div>
                  <StatusPill status={c.status} />
                  <ArrowUpRight
                    className="w-4 h-4 text-ink-faint group-hover:text-ink transition-colors shrink-0"
                    strokeWidth={1.75}
                  />
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ---- Active cases, compact ---- */}
      {active.length > 0 && (
        <section className="mb-16 sm:mb-20">
          <div className="flex items-end justify-between gap-6 mb-6">
            <h2 className="text-title">In progress</h2>
            <Link
              to="/cases"
              className="text-sm text-ink-muted hover:text-ink transition-colors underline underline-offset-4 decoration-line-strong"
            >
              All cases
            </Link>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            {active.slice(0, 4).map((c) => (
              <Link key={c.id} to={`/cases/${c.id}`} className="card-lift p-6 group block">
                <div className="flex items-start justify-between gap-4 mb-4">
                  <span className="pill-green">{c.sector_label || 'Classifying'}</span>
                  <span className="text-xs font-mono text-ink-faint">{c.reference}</span>
                </div>
                <h3 className="text-xl mb-2 leading-snug">{c.title}</h3>
                {c.current_stage && (
                  <p className="text-sm text-ink-muted leading-relaxed">
                    Stage {c.current_stage.index + 1} of {c.stage_count} &middot;{' '}
                    {c.current_stage.authority}
                  </p>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ---- How Hakk works: vertical rail, not a 3-card grid ---- */}
      <section className="mb-16 sm:mb-24">
        <div className="grid lg:grid-cols-[19rem_1fr] gap-10 lg:gap-16">
          <div className="lg:sticky lg:top-12 lg:self-start">
            <p className="eyebrow mb-4">How Hakk works</p>
            <h2 className="text-title mb-5">
              Four moves, and
              <span className="block italic text-powder-700">most of them are ours.</span>
            </h2>
            <p className="text-ink-muted leading-relaxed">
              The parts that need a human — the facts, the review, the approval — stay with you.
              Everything procedural belongs to the agent.
            </p>
          </div>

          <ol className="relative">
            <span
              className="absolute left-[1.4375rem] top-3 bottom-3 w-px bg-line"
              aria-hidden="true"
            />
            {STEPS.map(({ icon: Icon, title, body }, i) => (
              <li key={title} className="relative flex gap-6 pb-10 last:pb-0 group">
                <div className="relative z-10 w-12 h-12 shrink-0 rounded-2xl bg-surface border border-line grid place-items-center transition-all duration-220 ease-gentle group-hover:border-powder-300 group-hover:bg-powder-50">
                  <Icon
                    className="w-5 h-5 text-ink-muted transition-colors group-hover:text-powder-700"
                    strokeWidth={1.5}
                  />
                </div>
                <div className="pt-1.5 max-w-prose">
                  <div className="flex items-baseline gap-3 mb-2">
                    <span className="font-mono text-xs text-ink-faint">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <h3 className="text-xl">{title}</h3>
                  </div>
                  <p className="text-ink-soft leading-relaxed">{body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ---- This week in consumer rights ---- */}
      <section>
        <div className="flex items-end justify-between gap-6 mb-8">
          <div>
            <p className="eyebrow mb-3">This week in consumer rights</p>
            <h2 className="text-title">Worth knowing</h2>
          </div>
          <span className="hidden sm:inline-flex items-center gap-2 text-xs text-ink-faint">
            <Newspaper className="w-3.5 h-3.5" strokeWidth={1.75} />
            Placeholder feed
          </span>
        </div>

        {/* Stacked editorial list with hairline dividers — deliberately not a card grid. */}
        <div className="card overflow-hidden">
          {articles.map((a, i) => (
            <article
              key={a.title}
              className={`group px-6 sm:px-8 py-7 transition-colors duration-180 hover:bg-powder-50/50 ${
                i > 0 ? 'border-t border-line-soft' : ''
              }`}
            >
              <div className="grid sm:grid-cols-[9rem_1fr] gap-3 sm:gap-8">
                <div className="flex sm:flex-col gap-3 sm:gap-1.5 items-baseline sm:items-start">
                  <span className="pill-green shrink-0">{a.category}</span>
                  <time className="text-xs text-ink-faint">
                    {new Date(a.publishedAt).toLocaleDateString('en-IN', {
                      day: 'numeric',
                      month: 'short',
                    })}
                  </time>
                </div>
                <div className="min-w-0">
                  <h3 className="text-xl leading-snug mb-2 transition-colors group-hover:text-powder-800">
                    {a.title}
                  </h3>
                  <p className="text-ink-soft leading-relaxed mb-3 max-w-prose">{a.description}</p>
                  <p className="text-xs text-ink-faint">{a.source.name}</p>
                </div>
              </div>
            </article>
          ))}
        </div>

        <p className="mt-5 text-xs text-ink-faint flex items-center gap-2">
          <ShieldCheck className="w-3.5 h-3.5" strokeWidth={1.75} />
          Placeholder content shaped like a live news-API response — swapping in a real feed is a
          fetch change and nothing more.
        </p>
      </section>
    </div>
  );
}
