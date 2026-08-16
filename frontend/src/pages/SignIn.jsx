import { useState } from 'react';
import {
  ArrowRight,
  KeyRound,
  Mail,
  Phone,
  ShieldCheck,
  Terminal,
  User,
} from 'lucide-react';
import { api, setToken } from '../lib/api';
import { useAuth } from '../lib/AuthContext';
import { ErrorNote, Logo, Spinner, ThemeToggle } from '../components/ui';

/** Steps: details -> otp -> password (setup) ; or details -> password-login */
export default function SignIn() {
  const { signIn, setUser } = useAuth();
  const [step, setStep] = useState('details');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [hint, setHint] = useState('');
  const [delivery, setDelivery] = useState(null);
  const [sentTo, setSentTo] = useState(null);
  const [returning, setReturning] = useState(false);

  const [form, setForm] = useState({ phone: '', email: '', full_name: '' });
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [pendingUser, setPendingUser] = useState(null);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submitDetails(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await api.authStart(form);
      setReturning(res.returning_user);
      setHint(res.hint);
      setDelivery(res.delivery);
      setSentTo(res.sent_to);
      setStep('otp');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitOtp(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await api.authVerify({ phone: form.phone, code });
      if (res.needs_password_setup) {
        // Store the token so the next call authenticates, but hold back the
        // user — setting it here would route straight past password setup.
        setToken(res.token);
        setPendingUser(res.user);
        setStep('password');
      } else {
        signIn(res.token, res.user);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitPassword(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await api.authPassword(password);
      setUser(res.user || pendingUser);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitPasswordLogin(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await api.authLogin({ phone: form.phone, password });
      signIn(res.token, res.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.05fr_1fr] bg-canvas">
      {/* ---- Left: editorial panel, sage wash ---- */}
      <aside className="relative hidden lg:flex flex-col justify-between p-14 xl:p-18 wash-sage grain border-r border-line">
        <Logo size="lg" />

        <div className="max-w-lg animate-fade-up">
          <p className="eyebrow mb-6">Consumer disputes, resolved</p>
          <h1 className="text-display mb-7">
            The complaint you never
            <span className="block italic text-powder-700">got around to filing.</span>
          </h1>
          <p className="lede mb-10">
            Hakk drafts it in the right legal language, files it with the right authority, and
            escalates it the moment a statutory deadline lapses — without you having to remember
            any of them.
          </p>

          <dl className="space-y-5 border-l-2 border-powder-300 pl-6">
            {[
              ['48 hours', 'to acknowledge an e-commerce grievance, by rule'],
              ['30 days', 'before the RBI Ombudsman will hear a bank complaint'],
              ['2 years', 'before your right to file expires entirely'],
            ].map(([term, desc]) => (
              <div key={term}>
                <dt className="font-display text-xl text-powder-800">{term}</dt>
                <dd className="text-sm text-ink-muted">{desc}</dd>
              </div>
            ))}
          </dl>
        </div>

        <p className="text-xs text-ink-faint max-w-sm leading-relaxed">
          Hakk prepares and tracks complaints. It is not a law firm and does not provide legal
          advice.
        </p>
      </aside>

      {/* ---- Right: the form ---- */}
      <main className="relative flex items-center justify-center p-6 sm:p-12">
        <div className="absolute top-6 right-6 sm:top-8 sm:right-8">
          <ThemeToggle />
        </div>
        <div className="w-full max-w-[26rem] animate-fade-up">
          <div className="lg:hidden mb-10">
            <Logo />
          </div>

          <Stepper step={step} />

          {step === 'details' && (
            <form onSubmit={submitDetails} className="space-y-5">
              <header className="mb-8">
                <h2 className="text-title mb-2">Let's get you set up</h2>
                <p className="text-ink-muted leading-relaxed">
                  Your number and email are how authorities will reach you on the complaint.
                </p>
              </header>

              <Field
                icon={Phone}
                label="Mobile number"
                value={form.phone}
                onChange={set('phone')}
                placeholder="98765 43210"
                type="tel"
                autoComplete="tel"
                required
              />
              <Field
                icon={Mail}
                label="Email address"
                value={form.email}
                onChange={set('email')}
                placeholder="you@example.com"
                type="email"
                autoComplete="email"
                required
              />
              <Field
                icon={User}
                label="Full name"
                value={form.full_name}
                onChange={set('full_name')}
                placeholder="As it should appear on the complaint"
                autoComplete="name"
              />

              <ErrorNote onDismiss={() => setError('')}>{error}</ErrorNote>

              <button type="submit" disabled={busy} className="btn-primary w-full mt-2">
                {busy ? <Spinner /> : <ShieldCheck className="w-[18px] h-[18px]" strokeWidth={1.75} />}
                Send verification code
              </button>

              <button
                type="button"
                onClick={() => setStep('password-login')}
                className="btn-quiet w-full"
              >
                I already have a password
              </button>
            </form>
          )}

          {step === 'otp' && (
            <form onSubmit={submitOtp} className="space-y-5">
              <header className="mb-8">
                <h2 className="text-title mb-2">
                  {returning ? 'Welcome back' : delivery === 'email' ? 'Check your inbox' : 'Enter your code'}
                </h2>
                <p className="text-ink-muted leading-relaxed">
                  We sent a 6-digit code to{' '}
                  <span className="text-ink font-medium">{sentTo || form.email || form.phone}</span>.
                </p>
              </header>

              {delivery === 'console' && (
                <div className="flex items-start gap-3 rounded-2xl border border-clay-300/50 bg-clay-100 px-4 py-3.5">
                  <Terminal className="w-[18px] h-[18px] text-clay-700 shrink-0 mt-px" strokeWidth={1.75} />
                  <p className="text-[0.8125rem] text-clay-700 leading-relaxed">
                    <span className="font-semibold">Console delivery.</span> {hint}
                  </p>
                </div>
              )}

              <div>
                <label className="field-label">Verification code</label>
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="field text-center text-2xl tracking-[0.5em] font-mono"
                  placeholder="000000"
                  inputMode="numeric"
                  autoFocus
                  required
                />
              </div>

              <ErrorNote onDismiss={() => setError('')}>{error}</ErrorNote>

              <button
                type="submit"
                disabled={busy || code.length !== 6}
                className="btn-primary w-full"
              >
                {busy ? <Spinner /> : <ArrowRight className="w-[18px] h-[18px]" strokeWidth={1.75} />}
                Verify and continue
              </button>
              <button type="button" onClick={() => setStep('details')} className="btn-quiet w-full">
                Use a different number
              </button>
            </form>
          )}

          {step === 'password' && (
            <form onSubmit={submitPassword} className="space-y-5">
              <header className="mb-8">
                <h2 className="text-title mb-2">Set a password</h2>
                <p className="text-ink-muted leading-relaxed">
                  So you can get back into your cases without waiting for a code. At least 8
                  characters.
                </p>
              </header>

              <Field
                icon={KeyRound}
                label="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                placeholder="At least 8 characters"
                autoComplete="new-password"
                required
              />

              <ErrorNote onDismiss={() => setError('')}>{error}</ErrorNote>

              <button
                type="submit"
                disabled={busy || password.length < 8}
                className="btn-primary w-full"
              >
                {busy ? <Spinner /> : <ArrowRight className="w-[18px] h-[18px]" strokeWidth={1.75} />}
                Save and open my dashboard
              </button>
              <button
                type="button"
                onClick={() => setUser(pendingUser)}
                className="btn-quiet w-full"
              >
                Skip for now — I&rsquo;ll use a code each time
              </button>
            </form>
          )}

          {step === 'password-login' && (
            <form onSubmit={submitPasswordLogin} className="space-y-5">
              <header className="mb-8">
                <h2 className="text-title mb-2">Sign in</h2>
                <p className="text-ink-muted leading-relaxed">
                  Use the password you set on a previous visit.
                </p>
              </header>

              <Field
                icon={Phone}
                label="Mobile number"
                value={form.phone}
                onChange={set('phone')}
                placeholder="98765 43210"
                type="tel"
                autoComplete="tel"
                required
              />
              <Field
                icon={KeyRound}
                label="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                autoComplete="current-password"
                required
              />

              <ErrorNote onDismiss={() => setError('')}>{error}</ErrorNote>

              <button type="submit" disabled={busy} className="btn-primary w-full">
                {busy ? <Spinner /> : <ArrowRight className="w-[18px] h-[18px]" strokeWidth={1.75} />}
                Sign in
              </button>
              <button type="button" onClick={() => setStep('details')} className="btn-quiet w-full">
                Sign in with a code instead
              </button>
            </form>
          )}

          {hint && step === 'otp' && delivery === 'email' && (
            <p className="mt-8 text-xs text-ink-faint text-center leading-relaxed">
              {hint} It expires in 10 minutes — check spam if it hasn&rsquo;t arrived.
            </p>
          )}
        </div>
      </main>
    </div>
  );
}

function Stepper({ step }) {
  const order = ['details', 'otp', 'password'];
  const idx = order.indexOf(step);
  if (idx < 0) return <div className="mb-10" />;
  return (
    <div className="flex items-center gap-2 mb-10" aria-hidden="true">
      {order.map((s, i) => (
        <span
          key={s}
          className={`h-1 rounded-full transition-all duration-500 ease-gentle ${
            i <= idx ? 'bg-powder-400 w-10' : 'bg-line w-6'
          }`}
        />
      ))}
      <span className="ml-2 text-2xs uppercase tracking-[0.14em] text-ink-faint">
        Step {idx + 1} of 3
      </span>
    </div>
  );
}

function Field({ icon: Icon, label, ...props }) {
  return (
    <div>
      <label className="block text-sm font-medium text-ink-soft mb-2">{label}</label>
      <div className="relative">
        {Icon && (
          <Icon
            className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-ink-faint pointer-events-none"
            strokeWidth={1.75}
          />
        )}
        <input {...props} className={`field ${Icon ? 'pl-11' : ''}`} />
      </div>
    </div>
  );
}
