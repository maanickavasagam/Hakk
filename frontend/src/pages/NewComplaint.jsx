import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FileUp,
  Info,
  ListChecks,
  Mail,
  MessageCircle,
  Phone,
  Radar,
  ScanLine,
  Send,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import { api } from '../lib/api';
import { ErrorNote, PageLoader, SavedFlash, Spinner } from '../components/ui';

export default function NewComplaint() {
  const navigate = useNavigate();
  const [schema, setSchema] = useState(null);
  const [caseId, setCaseId] = useState(null);
  const [stepIdx, setStepIdx] = useState(0);
  const [answers, setAnswers] = useState({});
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(0);
  const [classifying, setClassifying] = useState(false);
  const [unclassified, setUnclassified] = useState(null);

  // 'choice' | 'freetext' | 'guided' — how intake started. Both freetext and
  // guided converge on the same `answers` state and the same step flow below;
  // freetext just pre-fills it via extraction before the steps ever render.
  const [intakeMode, setIntakeMode] = useState('choice');
  const [prefilled, setPrefilled] = useState(false);
  const [extractNote, setExtractNote] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const [s, created] = await Promise.all([api.intakeQuestions(), api.createCase(null)]);
        setSchema(s);
        setCaseId(created.id);
      } catch (err) {
        setError(err.message);
      }
    })();
  }, []);

  const persist = useCallback(
    async (partial) => {
      if (!caseId) return;
      setSaving(true);
      try {
        await api.saveAnswers(caseId, partial);
        setSavedAt(Date.now());
      } catch (err) {
        setError(err.message);
      } finally {
        setSaving(false);
      }
    },
    [caseId],
  );

  if (error && !schema) return <ErrorScreen message={error} />;
  if (!schema || !caseId) return <PageLoader label="Preparing your intake" />;

  // Steps: the guided questions, then documents, then review.
  const questionSteps = schema.steps;
  const totalSteps = questionSteps.length + 2;
  const isDocStep = stepIdx === questionSteps.length;
  const isReviewStep = stepIdx === questionSteps.length + 1;
  const step = questionSteps[stepIdx];

  const missing = step
    ? step.questions.filter((q) => q.required && !String(answers[q.id] ?? '').trim())
    : [];

  async function next() {
    if (step) {
      const partial = Object.fromEntries(
        step.questions.map((q) => [q.id, answers[q.id]]).filter(([, v]) => v),
      );
      await persist(partial);
    }
    setStepIdx((i) => Math.min(i + 1, totalSteps - 1));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function back() {
    setStepIdx((i) => Math.max(i - 1, 0));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function runClassification() {
    setClassifying(true);
    setError('');
    try {
      const res = await api.classify(caseId);
      if (res.classified) {
        navigate(`/cases/${caseId}?justClassified=1`);
      } else {
        setUnclassified(res);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setClassifying(false);
    }
  }

  if (unclassified) {
    return <UnclassifiedScreen result={unclassified} caseId={caseId} onRetry={() => setUnclassified(null)} />;
  }

  if (intakeMode === 'choice') {
    return (
      <IntakeChoiceScreen
        onGuided={() => setIntakeMode('guided')}
        onFreeText={() => setIntakeMode('freetext')}
      />
    );
  }

  if (intakeMode === 'freetext') {
    return (
      <FreeTextIntakeScreen
        caseId={caseId}
        onExtracted={(extracted, note) => {
          setAnswers((a) => ({ ...a, ...extracted }));
          setPrefilled(true);
          setExtractNote(note);
          setIntakeMode('guided');
        }}
        onUseGuidedInstead={() => setIntakeMode('guided')}
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 sm:px-10 py-12 sm:py-16">
      {/* progress rail */}
      <div className="mb-12">
        <div className="flex items-center justify-between mb-4">
          <p className="eyebrow">
            Step {stepIdx + 1} of {totalSteps}
          </p>
          <div className="flex items-center gap-3">
            {saving && <Spinner className="w-3.5 h-3.5 text-ink-faint" />}
            <SavedFlash show={savedAt} label="Answers saved" />
          </div>
        </div>
        <div className="flex gap-1.5" aria-hidden="true">
          {Array.from({ length: totalSteps }).map((_, i) => (
            <span
              key={i}
              className={`h-1 flex-1 rounded-full transition-all duration-500 ease-gentle ${
                i < stepIdx ? 'bg-powder-400' : i === stepIdx ? 'bg-powder-600' : 'bg-line'
              }`}
            />
          ))}
        </div>
      </div>

      <div key={stepIdx} className="animate-fade-up">
        {prefilled && stepIdx === 0 && (
          <div className="flex items-start gap-3 rounded-2xl border border-powder-200 bg-powder-50 px-5 py-4 mb-8">
            <Sparkles className="w-[18px] h-[18px] text-powder-700 shrink-0 mt-0.5" strokeWidth={1.75} />
            <div className="text-sm leading-relaxed">
              <p className="font-semibold text-powder-900 mb-1">
                Pre-filled from what you wrote — check each step and correct anything wrong.
              </p>
              {extractNote && <p className="text-powder-800">{extractNote}</p>}
            </div>
          </div>
        )}

        {step && (
          <>
            <header className="mb-10">
              <p className="eyebrow mb-3">{step.title}</p>
              <h1 className="text-title">
                {stepIdx === 0
                  ? 'Tell us what happened'
                  : stepIdx === 1
                    ? 'Who were you dealing with?'
                    : stepIdx === 2
                      ? 'When did this happen?'
                      : stepIdx === 3
                        ? 'What would make this right?'
                        : 'Have you already tried?'}
              </h1>
            </header>

            <div className="space-y-9">
              {step.questions.map((q) => (
                <Question
                  key={q.id}
                  q={q}
                  value={answers[q.id] ?? ''}
                  onChange={(v) => setAnswers((a) => ({ ...a, [q.id]: v }))}
                />
              ))}
            </div>
          </>
        )}

        {isDocStep && (
          <DocumentsStep
            caseId={caseId}
            documents={documents}
            setDocuments={setDocuments}
            onError={setError}
          />
        )}

        {isReviewStep && (
          <ReviewStep
            answers={answers}
            questionSteps={questionSteps}
            documents={documents}
            onJump={(i) => setStepIdx(i)}
          />
        )}
      </div>

      <ErrorNote onDismiss={() => setError('')}>{error}</ErrorNote>

      {/* nav */}
      <div className="flex items-center justify-between gap-4 mt-12 pt-8 hairline">
        <button onClick={back} disabled={stepIdx === 0} className="btn-ghost">
          <ArrowLeft className="w-4 h-4" strokeWidth={1.75} />
          Back
        </button>

        {isReviewStep ? (
          <button onClick={runClassification} disabled={classifying} className="btn-primary">
            {classifying ? <Spinner /> : <Radar className="w-[18px] h-[18px]" strokeWidth={1.75} />}
            {classifying ? 'Classifying your case…' : 'Classify and build my case'}
          </button>
        ) : (
          <button onClick={next} disabled={missing.length > 0 || saving} className="btn-primary">
            {isDocStep ? 'Review and continue' : 'Continue'}
            <ArrowRight className="w-[18px] h-[18px]" strokeWidth={1.75} />
          </button>
        )}
      </div>

      {missing.length > 0 && (
        <p className="mt-4 text-sm text-ink-muted text-right">
          Answer {missing.length === 1 ? 'the question' : `${missing.length} questions`} above to
          continue.
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

/** First screen: describe it in your own words, or answer fixed questions.
 *  Both paths land on the same guided steps — free text just arrives pre-filled. */
function IntakeChoiceScreen({ onGuided, onFreeText }) {
  return (
    <div className="max-w-3xl mx-auto px-6 sm:px-10 py-12 sm:py-16 animate-fade-up">
      <header className="mb-10">
        <p className="eyebrow mb-3">New complaint</p>
        <h1 className="text-title mb-4">How would you like to start?</h1>
        <p className="lede max-w-prose">
          Either way you&rsquo;ll end up reviewing the same details before anything is drafted.
        </p>
      </header>

      <div className="grid sm:grid-cols-2 gap-4">
        <button onClick={onFreeText} className="card-lift p-7 text-left group">
          <div className="w-11 h-11 rounded-2xl bg-powder-100 grid place-items-center mb-5">
            <Sparkles className="w-[18px] h-[18px] text-powder-700" strokeWidth={1.75} />
          </div>
          <h2 className="text-lg mb-2 group-hover:text-powder-800 transition-colors">
            Describe it in your own words
          </h2>
          <p className="text-sm text-ink-soft leading-relaxed">
            Write a few sentences the way you&rsquo;d tell a friend. Hakk pulls out the order,
            company, amount and dates — you check and correct them before anything is saved.
          </p>
        </button>

        <button onClick={onGuided} className="card-lift p-7 text-left group">
          <div className="w-11 h-11 rounded-2xl bg-canvas-sunk grid place-items-center mb-5">
            <ListChecks className="w-[18px] h-[18px] text-ink-soft" strokeWidth={1.75} />
          </div>
          <h2 className="text-lg mb-2 group-hover:text-powder-800 transition-colors">
            Answer guided questions
          </h2>
          <p className="text-sm text-ink-soft leading-relaxed">
            A fixed set of questions, one at a time. Nothing to write from scratch — pick from
            options and fill in the blanks.
          </p>
        </button>
      </div>
    </div>
  );
}

/** Free text in, extracted intake fields out — for the user to review on the
 *  guided steps next, not saved here. Falls back to the guided form on any
 *  extraction failure rather than leaving the user stuck. */
function FreeTextIntakeScreen({ caseId, onExtracted, onUseGuidedInstead }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError('');
    try {
      const res = await api.extractIntake(caseId, text);
      const note = res.understood
        ? res.clarifying_note
        : "This didn't read as a clear complaint yet — check every field below carefully, or start over.";
      onExtracted(res.answers, note);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 sm:px-10 py-12 sm:py-16 animate-fade-up">
      <header className="mb-8">
        <p className="eyebrow mb-3">In your own words</p>
        <h1 className="text-title mb-4">Tell us what happened</h1>
        <p className="lede max-w-prose">
          Company, amounts, dates, what you want — write it however feels natural. You&rsquo;ll
          get a chance to check and fix everything before it&rsquo;s saved.
        </p>
      </header>

      <form onSubmit={submit}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          autoFocus
          placeholder="I ordered a pair of headphones from Flipkart on 14 March for ₹2,500. They were never delivered even though tracking showed it as complete. I emailed support twice and they just told me to wait 48 hours — never heard back. I want a full refund."
          className="field resize-y text-[0.9375rem] leading-relaxed"
        />

        <ErrorNote onDismiss={() => setError('')}>{error}</ErrorNote>

        <div className="flex items-center justify-between gap-4 mt-6">
          <button type="button" onClick={onUseGuidedInstead} className="btn-quiet">
            Use guided questions instead
          </button>
          <button type="submit" disabled={busy || !text.trim()} className="btn-primary">
            {busy ? <Spinner /> : <Sparkles className="w-[18px] h-[18px]" strokeWidth={1.75} />}
            {busy ? 'Reading…' : 'Continue'}
          </button>
        </div>
      </form>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function Question({ q, value, onChange }) {
  const common = { id: q.id, value, onChange: (e) => onChange(e.target.value) };

  return (
    <div>
      <label htmlFor={q.id} className="field-label">
        {q.title}
        {!q.required && <span className="ml-2 text-sm font-sans text-ink-faint">Optional</span>}
      </label>
      {q.help && <span className="field-help">{q.help}</span>}

      {q.type === 'select' && (
        <div className="grid sm:grid-cols-2 gap-2.5">
          {q.options.map((opt) => {
            const active = value === opt;
            return (
              <button
                key={opt}
                type="button"
                onClick={() => onChange(opt)}
                className={`text-left rounded-2xl border px-4 py-3.5 text-[0.9375rem] leading-snug transition-all duration-180 ease-gentle ${
                  active
                    ? 'border-powder-400 bg-powder-50 text-powder-900 shadow-glow'
                    : 'border-line bg-surface text-ink-soft hover:border-powder-300 hover:bg-powder-50/50'
                }`}
              >
                <span className="flex items-start gap-2.5">
                  <span
                    className={`mt-1 w-4 h-4 rounded-full border-2 shrink-0 grid place-items-center transition-colors ${
                      active ? 'border-powder-600 bg-powder-600' : 'border-line-strong'
                    }`}
                  >
                    {active && <Check className="w-2.5 h-2.5 text-canvas" strokeWidth={3} />}
                  </span>
                  {opt}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {q.type === 'textarea' && (
        <textarea {...common} rows={5} placeholder={q.placeholder} className="field resize-y" />
      )}

      {(q.type === 'text' || q.type === 'number' || q.type === 'date') && (
        <input
          {...common}
          type={q.type}
          placeholder={q.placeholder}
          className={`field ${q.type === 'date' || q.type === 'number' ? 'max-w-xs' : ''}`}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function DocumentsStep({ caseId, documents, setDocuments, onError }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);

  const upload = async (files) => {
    setBusy(true);
    try {
      for (const file of files) {
        const doc = await api.uploadDocument(caseId, file);
        setDocuments((d) => [...d, doc]);
      }
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    try {
      await api.deleteDocument(caseId, id);
      setDocuments((d) => d.filter((x) => x.id !== id));
    } catch (err) {
      onError(err.message);
    }
  };

  return (
    <>
      <header className="mb-8">
        <p className="eyebrow mb-3">Evidence</p>
        <h1 className="text-title mb-4">Add your documents</h1>
        <p className="lede max-w-prose">
          Invoices, screenshots, bank statements, chat transcripts. Hakk reads them to pull out
          reference numbers and amounts so your complaint cites them precisely.
        </p>
      </header>

      {/* The completeness-not-authenticity disclaimer, stated plainly and up front. */}
      <div className="flex items-start gap-3 rounded-2xl border border-powder-200 bg-powder-50 px-5 py-4 mb-8">
        <Info className="w-[18px] h-[18px] text-powder-700 shrink-0 mt-0.5" strokeWidth={1.75} />
        <div className="text-sm leading-relaxed">
          <p className="font-semibold text-powder-900 mb-1">
            This is a completeness check, not an authenticity check.
          </p>
          <p className="text-powder-800">
            We read your documents only to find details worth citing — order IDs, amounts, dates.
            Hakk does <span className="font-medium">not</span> verify whether a document is genuine
            and makes no fraud or forgery assessment.
          </p>
        </div>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          upload(Array.from(e.dataTransfer.files));
        }}
        className={`rounded-3xl border-2 border-dashed px-8 py-14 text-center transition-all duration-220 ease-gentle ${
          drag ? 'border-powder-400 bg-powder-50' : 'border-line-strong bg-surface-warm'
        }`}
      >
        <div className="w-14 h-14 rounded-2xl bg-powder-100 grid place-items-center mx-auto mb-5">
          <FileUp className="w-6 h-6 text-powder-700" strokeWidth={1.5} />
        </div>
        <p className="text-lg mb-1.5 font-display">Drop files here</p>
        <p className="text-sm text-ink-muted mb-6">PDF, images or text — up to 15 MB each</p>
        <button onClick={() => inputRef.current?.click()} disabled={busy} className="btn-accent">
          {busy ? <Spinner /> : <FileUp className="w-[18px] h-[18px]" strokeWidth={1.75} />}
          {busy ? 'Reading…' : 'Choose files'}
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.txt,.csv,.md,.eml"
          onChange={(e) => {
            upload(Array.from(e.target.files));
            e.target.value = '';
          }}
        />
      </div>

      <div className="mt-6 space-y-4">
        {documents.map((doc) => (
          <DocumentCard
            key={doc.id}
            doc={doc}
            caseId={caseId}
            onConfirmed={(updated) =>
              setDocuments((d) => d.map((x) => (x.id === updated.id ? updated : x)))
            }
            onRemove={() => remove(doc.id)}
            onError={onError}
          />
        ))}
      </div>

      {documents.length === 0 && (
        <p className="mt-6 text-sm text-ink-muted text-center">
          You can continue without documents — but complaints that cite an order ID and an amount
          land much better.
        </p>
      )}
    </>
  );
}

/** Shows what was detected and lets the user confirm or correct every field. */
function DocumentCard({ doc, caseId, onConfirmed, onRemove, onError }) {
  const [fields, setFields] = useState(doc.fields);
  const [busy, setBusy] = useState(false);
  const confirmed = doc.is_confirmed;

  const update = (i, value) =>
    setFields((f) => f.map((x, j) => (j === i ? { ...x, value, display: value } : x)));

  const addField = () =>
    setFields((f) => [...f, { key: `custom_${f.length}`, label: 'Detail', value: '', display: '' }]);

  const confirm = async () => {
    setBusy(true);
    try {
      onConfirmed(await api.confirmDocument(caseId, doc.id, fields));
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={`card p-6 transition-colors duration-220 animate-scale-in ${
        confirmed ? 'border-powder-300 bg-powder-50/40' : ''
      }`}
    >
      <div className="flex items-start gap-4 mb-5">
        <div
          className={`w-10 h-10 rounded-xl grid place-items-center shrink-0 ${
            confirmed ? 'bg-powder-200' : 'bg-canvas-sunk'
          }`}
        >
          <ScanLine
            className={`w-[18px] h-[18px] ${confirmed ? 'text-powder-800' : 'text-ink-muted'}`}
            strokeWidth={1.75}
          />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink truncate">{doc.filename}</p>
          <p className="text-sm text-ink-muted mt-0.5">
            {(doc.size_bytes / 1024).toFixed(0)} KB &middot; read via{' '}
            <span className="font-mono text-xs">{doc.extraction_method}</span>
          </p>
        </div>
        {confirmed ? (
          <span className="pill-green shrink-0">
            <Check className="w-3 h-3" strokeWidth={2.5} />
            Confirmed
          </span>
        ) : (
          <button
            onClick={onRemove}
            className="text-ink-faint hover:text-rust-500 transition-colors shrink-0"
            aria-label="Remove document"
          >
            <Trash2 className="w-4 h-4" strokeWidth={1.75} />
          </button>
        )}
      </div>

      {fields.length > 0 ? (
        <>
          <p className="text-sm text-ink-soft mb-4">
            {confirmed
              ? 'You confirmed these details — they’ll be cited in your complaint.'
              : 'Here’s what we detected. Correct anything that’s wrong before confirming.'}
          </p>
          <div className="space-y-2.5">
            {fields.map((f, i) => (
              <div key={i} className="grid grid-cols-[9.5rem_1fr] gap-3 items-center">
                <label className="text-sm text-ink-muted truncate">{f.label}</label>
                <input
                  value={f.value}
                  onChange={(e) => update(i, e.target.value)}
                  disabled={confirmed}
                  className="field py-2 text-sm disabled:bg-canvas-sunk/60 disabled:text-ink-soft"
                />
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="text-sm text-ink-muted mb-4">{doc.extraction_note}</p>
      )}

      {!confirmed && (
        <div className="flex items-center gap-3 mt-5 pt-5 hairline">
          <button onClick={confirm} disabled={busy} className="btn-accent btn-sm">
            {busy ? <Spinner className="w-3.5 h-3.5" /> : <Check className="w-4 h-4" strokeWidth={2} />}
            Confirm these details
          </button>
          <button onClick={addField} className="btn-quiet">
            Add a detail manually
          </button>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function ReviewStep({ answers, questionSteps, documents, onJump }) {
  return (
    <>
      <header className="mb-10">
        <p className="eyebrow mb-3">Review</p>
        <h1 className="text-title mb-4">Does this look right?</h1>
        <p className="lede max-w-prose">
          Everything below goes into the classifier, which decides which regulator governs your
          complaint and which statute it cites.
        </p>
      </header>

      <div className="card divide-y divide-line-soft">
        {questionSteps.map((s, i) => (
          <section key={s.step} className="px-6 sm:px-8 py-6">
            <div className="flex items-center justify-between gap-4 mb-4">
              <p className="eyebrow">{s.title}</p>
              <button
                onClick={() => onJump(i)}
                className="text-sm text-ink-muted hover:text-powder-800 transition-colors underline underline-offset-4 decoration-line-strong"
              >
                Edit
              </button>
            </div>
            <dl className="space-y-3">
              {s.questions
                .filter((q) => answers[q.id])
                .map((q) => (
                  <div key={q.id} className="grid sm:grid-cols-[13rem_1fr] gap-1 sm:gap-6">
                    <dt className="text-sm text-ink-muted">{q.title}</dt>
                    <dd className="text-[0.9375rem] text-ink leading-relaxed">{answers[q.id]}</dd>
                  </div>
                ))}
              {s.questions.every((q) => !answers[q.id]) && (
                <p className="text-sm text-ink-faint italic">Nothing added</p>
              )}
            </dl>
          </section>
        ))}

        <section className="px-6 sm:px-8 py-6">
          <div className="flex items-center justify-between gap-4 mb-4">
            <p className="eyebrow">Documents</p>
            <button
              onClick={() => onJump(questionSteps.length)}
              className="text-sm text-ink-muted hover:text-powder-800 transition-colors underline underline-offset-4 decoration-line-strong"
            >
              Edit
            </button>
          </div>
          {documents.length ? (
            <ul className="space-y-2">
              {documents.map((d) => (
                <li key={d.id} className="flex items-center gap-2.5 text-[0.9375rem]">
                  <Check
                    className={`w-4 h-4 shrink-0 ${
                      d.is_confirmed ? 'text-powder-600' : 'text-ink-faint'
                    }`}
                    strokeWidth={2}
                  />
                  <span className="text-ink">{d.filename}</span>
                  <span className="text-sm text-ink-muted">
                    {d.fields.length} detail{d.fields.length === 1 ? '' : 's'}
                    {d.is_confirmed ? ' confirmed' : ' unconfirmed'}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-faint italic">No documents attached</p>
          )}
        </section>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */

/** Low confidence must never be a dead end: contact details plus a live chat box. */
function UnclassifiedScreen({ result, caseId, onRetry }) {
  const [messages, setMessages] = useState([
    {
      from: 'hakk',
      text: 'Tell us a bit more about your dispute and we’ll route it to the right person.',
    },
  ]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 9e9, behavior: 'smooth' });
  }, [messages]);

  const send = async (e) => {
    e.preventDefault();
    if (!draft.trim()) return;
    const text = draft.trim();
    setDraft('');
    setMessages((m) => [...m, { from: 'you', text }]);
    setBusy(true);
    try {
      const res = await api.supportChat(text);
      setMessages((m) => [...m, { from: 'hakk', text: res.reply }]);
    } catch {
      setMessages((m) => [
        ...m,
        { from: 'hakk', text: 'We couldn’t reach support just now — email or call us above.' },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 sm:px-10 py-12 sm:py-16 animate-fade-up">
      <header className="mb-10">
        <span className="pill-clay mb-5 inline-flex">Needs a human</span>
        <h1 className="text-title mb-4">We couldn&rsquo;t confidently classify this</h1>
        <p className="lede max-w-prose">
          Hakk placed your complaint at {Math.round(result.confidence * 100)}% confidence, below
          our {Math.round(result.threshold * 100)}% bar. Rather than file under the wrong statute,
          we&rsquo;re handing this to a person.
        </p>
      </header>

      <div className="panel p-6 mb-8">
        <p className="eyebrow mb-3">What the classifier saw</p>
        <p className="text-ink-soft leading-relaxed">{result.reasoning}</p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4 mb-10">
        <a
          href={`mailto:${result.contact.email}?subject=Help with my complaint`}
          className="card-lift p-6 flex items-start gap-4 group"
        >
          <div className="w-11 h-11 rounded-2xl bg-powder-100 grid place-items-center shrink-0">
            <Mail className="w-[18px] h-[18px] text-powder-700" strokeWidth={1.75} />
          </div>
          <div className="min-w-0">
            <p className="eyebrow mb-1.5">Email us</p>
            <p className="text-ink font-medium break-all group-hover:text-powder-800 transition-colors">
              {result.contact.email}
            </p>
            <p className="text-sm text-ink-muted mt-1">Replies within one working day</p>
          </div>
        </a>
        <a href={`tel:${result.contact.phone}`} className="card-lift p-6 flex items-start gap-4 group">
          <div className="w-11 h-11 rounded-2xl bg-powder-100 grid place-items-center shrink-0">
            <Phone className="w-[18px] h-[18px] text-powder-700" strokeWidth={1.75} />
          </div>
          <div className="min-w-0">
            <p className="eyebrow mb-1.5">Call us</p>
            <p className="text-ink font-medium group-hover:text-powder-800 transition-colors">
              {result.contact.phone}
            </p>
            <p className="text-sm text-ink-muted mt-1">Mon–Fri, 10am–6pm IST</p>
          </div>
        </a>
      </div>

      <div className="card overflow-hidden mb-8">
        <div className="px-6 py-4 border-b border-line-soft flex items-center gap-2.5">
          <MessageCircle className="w-[18px] h-[18px] text-powder-700" strokeWidth={1.75} />
          <p className="font-medium text-ink">Chat with us</p>
        </div>
        <div ref={scrollRef} className="px-6 py-5 space-y-4 max-h-72 overflow-y-auto">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.from === 'you' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-[0.9375rem] leading-relaxed animate-scale-in ${
                  m.from === 'you'
                    ? 'bg-powder-700 text-canvas rounded-br-md'
                    : 'bg-canvas-sunk text-ink rounded-bl-md'
                }`}
              >
                {m.text}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex justify-start">
              <div className="bg-canvas-sunk rounded-2xl rounded-bl-md px-4 py-3">
                <Spinner className="w-4 h-4 text-ink-muted" />
              </div>
            </div>
          )}
        </div>
        <form onSubmit={send} className="px-6 py-4 border-t border-line-soft flex gap-3">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Describe your dispute…"
            className="field py-2.5 text-sm flex-1"
          />
          <button type="submit" disabled={busy || !draft.trim()} className="btn-accent btn-sm">
            <Send className="w-4 h-4" strokeWidth={1.75} />
          </button>
        </form>
      </div>

      <div className="flex flex-wrap gap-3">
        <button onClick={onRetry} className="btn-ghost">
          <ArrowLeft className="w-4 h-4" strokeWidth={1.75} />
          Add more detail and retry
        </button>
        <a href={`/cases/${caseId}`} className="btn-quiet">
          View this case
        </a>
      </div>
    </div>
  );
}

function ErrorScreen({ message }) {
  return (
    <div className="max-w-lg mx-auto px-6 py-30 text-center animate-fade-up">
      <div className="w-14 h-14 rounded-2xl bg-rust-100 grid place-items-center mx-auto mb-5">
        <X className="w-6 h-6 text-rust-500" strokeWidth={1.75} />
      </div>
      <h2 className="text-title mb-3">Couldn&rsquo;t start your intake</h2>
      <p className="text-ink-muted mb-6">{message}</p>
      <button onClick={() => window.location.reload()} className="btn-primary">
        Try again
      </button>
    </div>
  );
}
