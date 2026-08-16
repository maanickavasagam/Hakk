import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BellRing,
  Check,
  CreditCard,
  Edit3,
  FileText,
  Lock,
  Radar,
  Scale,
  Send,
  Sparkles,
  Timer,
  Upload,
  X,
  Zap,
} from 'lucide-react';
import { api, rupees } from '../lib/api';
import { ErrorNote, PageLoader, Spinner, StatusPill } from '../components/ui';

const ICONS = {
  plus: FileText,
  edit: Edit3,
  upload: Upload,
  check: Check,
  target: Radar,
  route: Timer,
  timer: Timer,
  file: FileText,
  send: Send,
  card: CreditCard,
  alert: AlertTriangle,
  zap: Zap,
  bell: BellRing,
  lock: Lock,
  scale: Scale,
  trash: X,
  activity: Sparkles,
};

export default function CaseDetail() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [payFor, setPayFor] = useState(null);
  const [celebrate, setCelebrate] = useState(params.get('justClassified') === '1');
  const prevActivityCount = useRef(0);
  const [flashIds, setFlashIds] = useState(new Set());

  const load = useCallback(async () => {
    try {
      const c = await api.getCase(id);
      setData(c);
      return c;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  /** Live polling — the activity log updates on screen as the agent works. */
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const a = await api.activity(id);
        setData((prev) => {
          if (!prev) return prev;
          const known = new Set(prev.activity.map((x) => x.id));
          const fresh = a.activity.filter((x) => !known.has(x.id)).map((x) => x.id);
          if (fresh.length) {
            setFlashIds(new Set(fresh));
            setTimeout(() => setFlashIds(new Set()), 2600);
          }
          return {
            ...prev,
            activity: a.activity,
            stages: a.stages,
            drafts: a.drafts,
            status: a.status,
            current_stage_index: a.current_stage_index,
            lawyer_handoff: a.lawyer_handoff,
          };
        });
      } catch {
        /* keep quiet on transient failures */
      }
    }, 2500);
    return () => clearInterval(interval);
  }, [id]);

  useEffect(() => {
    if (!celebrate) return;
    const t = setTimeout(() => {
      setCelebrate(false);
      params.delete('justClassified');
      setParams(params, { replace: true });
    }, 6000);
    return () => clearTimeout(t);
  }, [celebrate, params, setParams]);

  if (!data && error) return <ErrorScreen message={error} />;
  if (!data) return <PageLoader label="Loading case" />;

  const stages = data.stages || [];
  const current = stages.find((s) => s.index === data.current_stage_index);
  const pendingDraft = [...(data.drafts || [])].reverse().find((d) => d.status === 'pending_review');

  return (
    <div className="max-w-shell mx-auto px-6 sm:px-10 py-10 sm:py-14">
      <Link
        to="/cases"
        className="inline-flex items-center gap-2 text-sm text-ink-muted hover:text-ink transition-colors mb-8"
      >
        <ArrowLeft className="w-4 h-4" strokeWidth={1.75} />
        All cases
      </Link>

      {celebrate && <ClassifiedBanner data={data} />}

      {/* ---- Header ---- */}
      <header className="grid lg:grid-cols-[1fr_auto] gap-8 items-start mb-12 animate-fade-up">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <StatusPill status={data.status} />
            {data.sector_label && <span className="pill-green">{data.sector_label}</span>}
            <span className="font-mono text-xs text-ink-faint">{data.reference}</span>
          </div>
          <h1 className="text-title mb-3">{data.title}</h1>
          {data.primary_statute && (
            <p className="text-ink-muted">
              Governed by <span className="text-ink-soft">{data.primary_statute}</span>
              {data.confidence != null && (
                <span className="text-ink-faint">
                  {' '}
                  &middot; classified at {Math.round(data.confidence * 100)}% confidence
                </span>
              )}
            </p>
          )}
        </div>

        {data.status === 'active' && (
          <button
            onClick={async () => {
              try {
                setData(await api.markUnresponsive(id));
              } catch (err) {
                setError(err.message);
              }
            }}
            className="btn-ghost shrink-0"
          >
            <Scale className="w-4 h-4" strokeWidth={1.75} />
            Still no response — get a lawyer
          </button>
        )}
      </header>

      <ErrorNote onDismiss={() => setError('')}>{error}</ErrorNote>

      {data.lawyer_handoff && <HandoffCard reason={data.handoff_reason} />}

      <div className="grid lg:grid-cols-[minmax(0,1fr)_23rem] gap-10 xl:gap-14">
        {/* ---- Left column ---- */}
        <div className="min-w-0 space-y-14">
          {pendingDraft && (
            <DraftPanel
              caseId={id}
              draft={pendingDraft}
              stage={stages.find((s) => s.id === pendingDraft.stage_id)}
              onChanged={load}
              onError={setError}
            />
          )}

          <section>
            <div className="flex items-end justify-between gap-6 mb-7">
              <div>
                <p className="eyebrow mb-2">The full ladder, mapped up front</p>
                <h2 className="text-title">Case timeline</h2>
              </div>
              {stages.some((s) => !s.paid) && (
                <button onClick={() => setPayFor('bundle')} className="btn-ghost">
                  <CreditCard className="w-4 h-4" strokeWidth={1.75} />
                  Unlock all stages
                </button>
              )}
            </div>

            <ol className="relative">
              <span
                className="absolute left-[1.4375rem] top-4 bottom-4 w-px bg-line"
                aria-hidden="true"
              />
              {stages.map((s) => (
                <StageRow
                  key={s.id}
                  stage={s}
                  caseId={id}
                  isCurrent={s.index === data.current_stage_index}
                  drafts={(data.drafts || []).filter((d) => d.stage_id === s.id)}
                  onUnlock={() => setPayFor(s)}
                  onChanged={setData}
                  onError={setError}
                />
              ))}
            </ol>
          </section>

          {data.documents?.length > 0 && <DocumentsSummary documents={data.documents} />}
        </div>

        {/* ---- Right column: the activity log ---- */}
        <aside className="lg:sticky lg:top-8 lg:self-start">
          <ActivityLog activity={data.activity || []} flashIds={flashIds} current={current} />
        </aside>
      </div>

      {payFor && (
        <PayModal
          caseId={id}
          target={payFor}
          bundlePrice={data.bundle_price_paise}
          onClose={() => setPayFor(null)}
          onPaid={load}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function ClassifiedBanner({ data }) {
  return (
    <div className="rounded-3xl border border-powder-300 bg-powder-50 p-6 sm:p-8 mb-10 animate-scale-in">
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 rounded-2xl bg-powder-200 grid place-items-center shrink-0">
          <Radar className="w-5 h-5 text-powder-800" strokeWidth={1.75} />
        </div>
        <div className="min-w-0">
          <h2 className="text-xl mb-2">
            Classified as {data.sector_label} at {Math.round(data.confidence * 100)}% confidence
          </h2>
          <p className="text-powder-900/85 leading-relaxed mb-3">
            {data.classification_reasoning}
          </p>
          <p className="text-sm text-powder-800">
            Your full {data.stage_count}-stage timeline is mapped below, and the Stage 1 draft is
            ready for review.
          </p>
        </div>
      </div>
    </div>
  );
}

function HandoffCard({ reason }) {
  return (
    <div className="rounded-3xl border border-rust-300/60 bg-rust-100/60 p-6 sm:p-8 mb-10 animate-scale-in">
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 rounded-2xl bg-rust-100 border border-rust-300/50 grid place-items-center shrink-0">
          <Scale className="w-5 h-5 text-rust-500" strokeWidth={1.75} />
        </div>
        <div>
          <h2 className="text-xl mb-2">Flagged for a lawyer</h2>
          <p className="text-ink-soft leading-relaxed mb-2">{reason}</p>
          <p className="text-sm text-ink-muted">
            Lawyer matching is a later phase — for now this case carries the handoff flag and our
            team picks it up.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function StageRow({ stage, caseId, isCurrent, drafts, onUnlock, onChanged, onError }) {
  const locked = !stage.paid;
  const lapsed = stage.status === 'lapsed';
  const Icon = lapsed ? AlertTriangle : locked ? Lock : isCurrent ? Timer : Check;

  return (
    <li className="relative flex gap-6 pb-8 last:pb-0">
      <div
        className={`relative z-10 w-12 h-12 shrink-0 rounded-2xl grid place-items-center border transition-all duration-220 ease-gentle ${
          isCurrent
            ? 'bg-powder-100 border-powder-300 shadow-glow'
            : lapsed
              ? 'bg-rust-100 border-rust-300/60'
              : locked
                ? 'bg-canvas-sunk border-line'
                : 'bg-surface border-line'
        }`}
      >
        <Icon
          className={`w-5 h-5 ${
            isCurrent
              ? 'text-powder-800'
              : lapsed
                ? 'text-rust-500'
                : locked
                  ? 'text-ink-faint'
                  : 'text-powder-600'
          }`}
          strokeWidth={1.75}
        />
      </div>

      <div
        className={`flex-1 min-w-0 rounded-3xl border p-6 transition-all duration-220 ease-gentle ${
          isCurrent ? 'border-powder-300 bg-powder-50/40 shadow-soft' : 'border-line bg-surface'
        } ${locked ? 'opacity-75' : ''}`}
      >
        <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
          <div className="min-w-0">
            <p className="eyebrow mb-1.5">Stage {stage.index + 1}</p>
            <h3 className="text-xl leading-snug">{stage.name}</h3>
            <p className="text-sm text-ink-muted mt-1">{stage.authority}</p>
          </div>
          <StatusPill status={stage.status} />
        </div>

        <p className="text-ink-soft leading-relaxed mb-5">{stage.summary}</p>

        {/* Statutory window + live countdown */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mb-5">
          <span className="inline-flex items-center gap-2 text-sm">
            <Timer className="w-4 h-4 text-ink-faint" strokeWidth={1.75} />
            <span className="text-ink-soft">
              <span className="font-medium text-ink">{stage.deadline_days} days</span> to resolve
            </span>
          </span>
          {stage.ack_hours && (
            <span className="text-sm text-ink-soft">
              <span className="font-medium text-ink">{stage.ack_hours} hours</span> to acknowledge
            </span>
          )}
          {isCurrent && stage.deadline_at && stage.status === 'awaiting_response' && (
            <Countdown deadlineAt={stage.deadline_at} />
          )}
        </div>

        {/* Acknowledgement state — a separate, shorter duty from redressal. */}
        {stage.ack_hours && (stage.acknowledged_at || stage.ack_breached) && (
          <div
            className={`flex items-start gap-2.5 rounded-2xl px-4 py-3 mb-5 text-sm ${
              stage.acknowledged_at
                ? 'bg-powder-50 border border-powder-200 text-powder-900'
                : 'bg-clay-100 border border-clay-300/50 text-clay-700'
            }`}
          >
            {stage.acknowledged_at ? (
              <Check className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={2} />
            ) : (
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.75} />
            )}
            <p className="leading-relaxed">
              {stage.acknowledged_at
                ? `Acknowledged. The ${stage.deadline_days}-day window to actually resolve it keeps running.`
                : `No acknowledgement inside the ${stage.ack_hours} hours the regulation requires. That breach is on record and gets cited in the next escalation — the ${stage.deadline_days}-day redressal window is unaffected.`}
            </p>
          </div>
        )}

        {/* Legal basis */}
        <div className="rounded-2xl bg-canvas-sunk/70 border border-line-soft px-5 py-4 mb-5">
          <p className="eyebrow mb-2">Legal basis</p>
          <p className="text-sm font-medium text-ink mb-2">{stage.regulation}</p>
          <p className="text-sm text-ink-muted leading-relaxed">{stage.regulation_note}</p>
        </div>

        {/* Documents needed, shown ahead of time */}
        <details className="group">
          <summary className="cursor-pointer list-none text-sm text-ink-muted hover:text-ink transition-colors inline-flex items-center gap-2">
            <Upload className="w-3.5 h-3.5" strokeWidth={1.75} />
            Documents typically needed here ({stage.required_documents.length})
          </summary>
          <ul className="mt-3 space-y-1.5 pl-6">
            {stage.required_documents.map((d) => (
              <li key={d} className="text-sm text-ink-soft list-disc marker:text-powder-400">
                {d}
              </li>
            ))}
          </ul>
        </details>

        {drafts.length > 0 && (
          <div className="mt-5 pt-5 hairline flex flex-wrap items-center gap-3">
            {drafts.map((d) => (
              <span key={d.id} className="inline-flex items-center gap-2 text-sm text-ink-muted">
                <FileText className="w-3.5 h-3.5" strokeWidth={1.75} />
                Draft #{d.id}
                {d.auto_generated && (
                  <span className="pill-green">
                    <Zap className="w-3 h-3" strokeWidth={2} />
                    Auto
                  </span>
                )}
                <StatusPill status={d.status} />
              </span>
            ))}
          </div>
        )}

        {isCurrent && stage.status === 'awaiting_response' && (
          <ResponsePanel caseId={caseId} stage={stage} onChanged={onChanged} onError={onError} />
        )}

        {stage.outcome_note && !isCurrent && (
          <div className="mt-5 pt-5 hairline">
            <p className="eyebrow mb-1.5">What they said</p>
            <p className="text-sm text-ink-soft leading-relaxed italic">
              &ldquo;{stage.outcome_note}&rdquo;
            </p>
          </div>
        )}

        {locked && (
          <div className="mt-5 pt-5 hairline flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-ink-muted">
              Unlock to have Hakk draft and file this stage automatically.
            </p>
            <button onClick={onUnlock} className="btn-accent btn-sm">
              <CreditCard className="w-4 h-4" strokeWidth={1.75} />
              Unlock for {rupees(stage.price_paise)}
            </button>
          </div>
        )}
      </div>
    </li>
  );
}

/**
 * Waiting out the clock is only correct while the company is silent. The moment
 * they reject or fob you off, every ladder Hakk carries treats that as the
 * trigger for the next rung — so recording it here escalates immediately rather
 * than burning the rest of the window.
 */
function ResponsePanel({ caseId, stage, onChanged, onError }) {
  const [open, setOpen] = useState(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (outcome) => {
    setBusy(true);
    try {
      onChanged(await api.recordResponse(caseId, stage.id, outcome, note));
      setOpen(null);
      setNote('');
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const acknowledge = async () => {
    setBusy(true);
    try {
      onChanged(await api.recordAcknowledgement(caseId, stage.id, null));
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const OPTIONS = [
    {
      key: 'rejected',
      label: 'They rejected it',
      icon: X,
      blurb: `A rejection opens the next rung straight away under ${stage.regulation} — Hakk will escalate now instead of waiting out the remaining ${stage.deadline_days} days.`,
    },
    {
      key: 'unsatisfactory',
      label: 'They replied, but it does not fix it',
      icon: AlertTriangle,
      blurb: `An inadequate reply counts the same as a refusal here. Hakk escalates now rather than running down the ${stage.deadline_days}-day window.`,
    },
    {
      key: 'resolved',
      label: 'They resolved it',
      icon: Check,
      blurb: 'This closes the case. Nothing further is drafted or scheduled.',
    },
  ];

  return (
    <div className="mt-5 pt-5 hairline">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <p className="text-sm text-ink-muted">Heard back from {stage.authority}?</p>
        {stage.ack_hours && !stage.acknowledged_at && (
          <button onClick={acknowledge} disabled={busy} className="btn-quiet !px-2 text-xs">
            <Check className="w-3.5 h-3.5" strokeWidth={2} />
            They acknowledged it
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {OPTIONS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setOpen(open === key ? null : key)}
            className={`btn btn-sm border px-4 py-2 ${
              open === key
                ? 'border-powder-400 bg-powder-100 text-powder-900'
                : 'border-line text-ink-soft bg-surface hover:border-powder-300 hover:text-powder-800'
            }`}
          >
            <Icon className="w-3.5 h-3.5" strokeWidth={1.75} />
            {label}
          </button>
        ))}
      </div>

      {open && (
        <div className="mt-4 animate-scale-in">
          <p className="text-sm text-ink-muted leading-relaxed mb-3">
            {OPTIONS.find((o) => o.key === open).blurb}
          </p>
          <label className="field-help !mb-2">
            Paste what they actually said, if you have it — the next letter quotes it back.
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            className="field resize-y"
            placeholder="e.g. Refund denied as the return window had closed."
          />
          <div className="flex items-center gap-3 mt-3">
            <button
              onClick={() => submit(open)}
              disabled={busy}
              className={open === 'resolved' ? 'btn-accent btn-sm' : 'btn-primary btn-sm'}
            >
              {busy ? <Spinner /> : <ArrowRight className="w-4 h-4" strokeWidth={1.75} />}
              {open === 'resolved' ? 'Close this case' : 'Record and escalate now'}
            </button>
            <button onClick={() => setOpen(null)} className="btn-quiet text-sm">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Ticking countdown against the compressed demo clock. */
function Countdown({ deadlineAt }) {
  const target = useMemo(() => new Date(deadlineAt).getTime(), [deadlineAt]);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, []);

  const remaining = Math.max(0, target - now);
  const s = Math.floor(remaining / 1000);
  const label =
    s >= 3600
      ? `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
      : s >= 60
        ? `${Math.floor(s / 60)}m ${s % 60}s`
        : `${s}s`;
  const urgent = remaining < 15000;

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-mono transition-colors ${
        remaining === 0
          ? 'bg-rust-100 text-rust-700'
          : urgent
            ? 'bg-clay-100 text-clay-700 animate-pulse-soft'
            : 'bg-powder-100 text-powder-800'
      }`}
    >
      <Timer className="w-3.5 h-3.5" strokeWidth={2} />
      {remaining === 0 ? 'Deadline reached' : `${label} left`}
    </span>
  );
}

/* ------------------------------------------------------------------ */

function DraftPanel({ caseId, draft, stage, onChanged, onError }) {
  const [body, setBody] = useState(draft.body);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setBody(draft.body);
    setEditing(false);
  }, [draft.id, draft.body]);

  const save = async () => {
    setBusy(true);
    try {
      await api.editDraft(caseId, draft.id, { body });
      setEditing(false);
      await onChanged();
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    setBusy(true);
    try {
      if (body !== draft.body) await api.editDraft(caseId, draft.id, { body });
      await api.approveDraft(caseId, draft.id);
      await onChanged();
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="animate-fade-up">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div>
          <p className="eyebrow mb-2">
            {draft.auto_generated ? 'Auto-generated escalation' : 'Ready for your review'}
          </p>
          <h2 className="text-title">
            Stage {stage ? stage.index + 1 : ''} draft
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {draft.auto_generated && (
            <span className="pill-green">
              <Zap className="w-3 h-3" strokeWidth={2} />
              Written by the agent
            </span>
          )}
          <span className="pill-neutral">via {draft.generated_by}</span>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="px-6 sm:px-8 py-5 border-b border-line-soft bg-surface-warm">
          <p className="eyebrow mb-2">Citing</p>
          <p className="font-medium text-ink">{draft.legal_basis}</p>
        </div>

        {editing ? (
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={26}
            className="w-full px-6 sm:px-8 py-6 font-mono text-[0.8125rem] leading-relaxed text-ink bg-surface resize-y focus:outline-none"
          />
        ) : (
          <pre className="px-6 sm:px-8 py-6 whitespace-pre-wrap font-sans text-[0.9375rem] leading-[1.75] text-ink max-h-[34rem] overflow-y-auto">
            {body}
          </pre>
        )}

        <div className="px-6 sm:px-8 py-5 border-t border-line-soft bg-surface-warm flex flex-wrap items-center justify-between gap-4">
          <p className="text-sm text-ink-muted">
            Nothing is sent until you approve it.
          </p>
          <div className="flex flex-wrap gap-3">
            {editing ? (
              <>
                <button
                  onClick={() => {
                    setBody(draft.body);
                    setEditing(false);
                  }}
                  className="btn-ghost btn-sm"
                >
                  Cancel
                </button>
                <button onClick={save} disabled={busy} className="btn-ghost btn-sm">
                  {busy ? <Spinner className="w-3.5 h-3.5" /> : <Check className="w-4 h-4" strokeWidth={2} />}
                  Save edits
                </button>
              </>
            ) : (
              <button onClick={() => setEditing(true)} className="btn-ghost btn-sm">
                <Edit3 className="w-4 h-4" strokeWidth={1.75} />
                Edit draft
              </button>
            )}
            <button onClick={approve} disabled={busy} className="btn-primary !py-2.5 !px-5 !text-sm">
              {busy ? <Spinner className="w-3.5 h-3.5" /> : <Send className="w-4 h-4" strokeWidth={1.75} />}
              Approve and file
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */

function DocumentsSummary({ documents }) {
  return (
    <section>
      <h2 className="text-title mb-6">Evidence on file</h2>
      <div className="card divide-y divide-line-soft">
        {documents.map((d) => (
          <div key={d.id} className="px-6 py-5">
            <div className="flex items-center justify-between gap-4 mb-3">
              <p className="font-medium text-ink truncate">{d.filename}</p>
              {d.is_confirmed ? (
                <span className="pill-green shrink-0">
                  <Check className="w-3 h-3" strokeWidth={2.5} />
                  Confirmed
                </span>
              ) : (
                <span className="pill-clay shrink-0">Unconfirmed</span>
              )}
            </div>
            {d.fields.length > 0 ? (
              <div className="flex flex-wrap gap-x-6 gap-y-1.5">
                {d.fields.map((f, i) => (
                  <span key={i} className="text-sm">
                    <span className="text-ink-muted">{f.label}: </span>
                    <span className="text-ink font-medium">{f.display || f.value}</span>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-ink-faint">{d.extraction_note}</p>
            )}
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-ink-faint">
        Completeness check only — Hakk does not assess whether a document is authentic.
      </p>
    </section>
  );
}

/* ------------------------------------------------------------------ */

function ActivityLog({ activity, flashIds, current }) {
  return (
    <div className="card overflow-hidden">
      <div className="px-6 py-5 border-b border-line-soft">
        <div className="flex items-center justify-between gap-3 mb-1">
          <h2 className="font-display text-xl">Activity log</h2>
          <span className="inline-flex items-center gap-1.5 text-2xs uppercase tracking-wider text-powder-700">
            <span className="w-1.5 h-1.5 rounded-full bg-powder-500 animate-pulse-soft" />
            Live
          </span>
        </div>
        <p className="text-sm text-ink-muted leading-relaxed">
          Every automated action, recorded as it happens.
        </p>
      </div>

      {current && current.status === 'awaiting_response' && current.deadline_at && (
        <div className="px-6 py-4 bg-powder-50 border-b border-powder-200">
          <p className="eyebrow mb-2">Watching now</p>
          <p className="text-sm text-ink-soft leading-relaxed mb-3">
            Stage {current.index + 1} &middot; {current.authority}
          </p>
          <Countdown deadlineAt={current.deadline_at} />
        </div>
      )}

      <ol className="max-h-[32rem] overflow-y-auto">
        {activity.map((a, i) => {
          const Icon = ICONS[a.icon] || Sparkles;
          const flash = flashIds.has(a.id);
          const isAgent = a.actor === 'agent';
          return (
            <li
              key={a.id}
              className={`relative flex gap-3.5 px-6 py-4 transition-colors duration-500 ${
                i > 0 ? 'border-t border-line-soft' : ''
              } ${flash ? 'bg-powder-100' : ''}`}
            >
              <div
                className={`w-8 h-8 rounded-xl grid place-items-center shrink-0 mt-0.5 ${
                  isAgent
                    ? 'bg-powder-200'
                    : a.actor === 'user'
                      ? 'bg-canvas-sunk'
                      : 'bg-powder-50 border border-powder-200'
                }`}
              >
                <Icon
                  className={`w-4 h-4 ${isAgent ? 'text-powder-800' : 'text-ink-muted'}`}
                  strokeWidth={1.75}
                />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-sm font-medium text-ink leading-snug">{a.event}</p>
                  <time className="text-2xs text-ink-faint shrink-0 font-mono">
                    {new Date(a.created_at).toLocaleTimeString('en-IN', {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </time>
                </div>
                {a.detail && (
                  <p className="text-[0.8125rem] text-ink-muted leading-relaxed mt-1">{a.detail}</p>
                )}
                <span
                  className={`inline-block mt-1.5 text-2xs uppercase tracking-wider ${
                    isAgent ? 'text-powder-700' : 'text-ink-faint'
                  }`}
                >
                  {a.actor}
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function PayModal({ caseId, target, bundlePrice, onClose, onPaid }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const isBundle = target === 'bundle';
  const amount = isBundle ? bundlePrice : target.price_paise;

  const pay = async () => {
    setBusy(true);
    setErr('');
    try {
      await api.pay(caseId, isBundle ? { kind: 'bundle' } : { kind: 'single', stage_id: target.id });
      await onPaid();
      onClose();
    } catch (e) {
      setErr(e.message);
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-6 bg-ink/25 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="card w-full max-w-md p-8 shadow-float animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <p className="eyebrow mb-2">Mock checkout</p>
            <h2 className="text-2xl">
              {isBundle ? 'Unlock every remaining stage' : `Unlock Stage ${target.index + 1}`}
            </h2>
          </div>
          <button onClick={onClose} className="text-ink-faint hover:text-ink transition-colors">
            <X className="w-5 h-5" strokeWidth={1.75} />
          </button>
        </div>

        {!isBundle && (
          <div className="panel p-5 mb-6">
            <p className="font-medium text-ink mb-1">{target.name}</p>
            <p className="text-sm text-ink-muted">{target.authority}</p>
          </div>
        )}

        <div className="flex items-baseline justify-between mb-6 pb-6 hairline">
          <span className="text-ink-soft">Amount</span>
          <span className="font-display text-4xl text-ink">{rupees(amount)}</span>
        </div>

        <p className="text-sm text-ink-muted leading-relaxed mb-6">
          Once unlocked, Hakk drafts this stage and files it automatically the moment the previous
          deadline lapses — you review before anything goes out.
        </p>

        <div className="rounded-2xl bg-clay-100/70 border border-clay-300/40 px-4 py-3 mb-6">
          <p className="text-[0.8125rem] text-clay-700 leading-relaxed">
            <span className="font-semibold">Mock payment.</span> No gateway is connected — clicking
            Pay marks this unlocked in the database instantly.
          </p>
        </div>

        <ErrorNote>{err}</ErrorNote>

        <button onClick={pay} disabled={busy} className="btn-primary w-full mt-2">
          {busy ? <Spinner /> : <CreditCard className="w-[18px] h-[18px]" strokeWidth={1.75} />}
          Pay {rupees(amount)}
        </button>
      </div>
    </div>
  );
}

function ErrorScreen({ message }) {
  return (
    <div className="max-w-lg mx-auto px-6 py-30 text-center">
      <h2 className="text-title mb-3">Couldn&rsquo;t load this case</h2>
      <p className="text-ink-muted mb-6">{message}</p>
      <Link to="/cases" className="btn-primary">
        Back to cases
      </Link>
    </div>
  );
}
