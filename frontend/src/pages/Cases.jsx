import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, FilePlus2, FolderOpen } from 'lucide-react';
import { api } from '../lib/api';
import { Empty, PageLoader, StatusPill } from '../components/ui';

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'unclassified', label: 'Needs review' },
  { key: 'lawyer_handoff', label: 'Lawyer handoff' },
  { key: 'intake', label: 'Drafts' },
];

export default function Cases() {
  const [cases, setCases] = useState(null);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    api.listCases().then((d) => setCases(d.cases)).catch(() => setCases([]));
  }, []);

  if (cases === null) return <PageLoader label="Loading your cases" />;

  const shown = filter === 'all' ? cases : cases.filter((c) => c.status === filter);
  const counts = Object.fromEntries(
    FILTERS.map((f) => [
      f.key,
      f.key === 'all' ? cases.length : cases.filter((c) => c.status === f.key).length,
    ]),
  );

  return (
    <div className="max-w-shell mx-auto px-6 sm:px-10 py-12 sm:py-16">
      <header className="flex flex-wrap items-end justify-between gap-6 mb-10 animate-fade-up">
        <div>
          <p className="eyebrow mb-3">Your case file</p>
          <h1 className="text-title">My Cases</h1>
        </div>
        <Link to="/new" className="btn-primary">
          <FilePlus2 className="w-[18px] h-[18px]" strokeWidth={1.75} />
          Start new complaint
        </Link>
      </header>

      {cases.length === 0 ? (
        <Empty
          icon={FolderOpen}
          title="No cases yet"
          body="When you file your first complaint it will live here, with its timeline, drafts and activity log."
          action={
            <Link to="/new" className="btn-primary">
              <FilePlus2 className="w-[18px] h-[18px]" strokeWidth={1.75} />
              Start your first complaint
            </Link>
          }
        />
      ) : (
        <>
          <div className="flex flex-wrap gap-2 mb-8">
            {FILTERS.filter((f) => counts[f.key] > 0 || f.key === 'all').map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`rounded-full px-4 py-2 text-sm transition-all duration-180 ease-gentle ${
                  filter === f.key
                    ? 'bg-powder-200 text-powder-900 font-medium'
                    : 'text-ink-muted hover:bg-canvas-sunk hover:text-ink'
                }`}
              >
                {f.label}
                {/* ink-faint is for decorative meta; this is a real count the
                    user reads, and at ~2.3:1 it failed contrast in both themes. */}
                <span className="ml-2 text-ink-muted">{counts[f.key]}</span>
              </button>
            ))}
          </div>

          <div className="card divide-y divide-line-soft overflow-hidden">
            {shown.map((c) => (
              <Link
                key={c.id}
                to={`/cases/${c.id}`}
                className="group flex flex-wrap items-center gap-x-6 gap-y-3 px-6 sm:px-8 py-6 transition-colors duration-180 hover:bg-powder-50/50"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-3 mb-2">
                    <StatusPill status={c.status} />
                    {c.sector_label && <span className="pill-neutral">{c.sector_label}</span>}
                    <span className="font-mono text-xs text-ink-faint">{c.reference}</span>
                  </div>
                  <h2 className="text-xl leading-snug transition-colors group-hover:text-powder-800">
                    {c.title}
                  </h2>
                  {c.current_stage ? (
                    <p className="text-sm text-ink-muted mt-1.5">
                      Stage {c.current_stage.index + 1} of {c.stage_count} &middot;{' '}
                      {c.current_stage.authority}
                    </p>
                  ) : (
                    <p className="text-sm text-ink-muted mt-1.5">
                      {c.status === 'intake' ? 'Intake not finished' : 'Awaiting classification'}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <time className="text-sm text-ink-faint">
                    {new Date(c.updated_at).toLocaleDateString('en-IN', {
                      day: 'numeric',
                      month: 'short',
                    })}
                  </time>
                  <ArrowUpRight
                    className="w-4 h-4 text-ink-faint transition-all duration-180 group-hover:text-powder-700 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                    strokeWidth={1.75}
                  />
                </div>
              </Link>
            ))}
          </div>

          {shown.length === 0 && (
            <p className="text-center py-16 text-ink-muted">No cases in this view.</p>
          )}
        </>
      )}
    </div>
  );
}
