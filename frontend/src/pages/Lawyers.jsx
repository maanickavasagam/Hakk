import { Link } from 'react-router-dom';
import { ArrowRight, MapPin, Scale, ShieldCheck, Star } from 'lucide-react';

/** Stub screen. The handoff flag is real and set by the backend; matching lands later. */
export default function Lawyers() {
  return (
    <div className="max-w-shell mx-auto px-6 sm:px-10 py-12 sm:py-16">
      <header className="grid lg:grid-cols-[1.3fr_1fr] gap-10 lg:gap-16 items-end mb-14 animate-fade-up">
        <div>
          <span className="pill-clay mb-5 inline-flex">Coming soon</span>
          <h1 className="text-display mb-6">
            When the ladder runs out,
            <span className="block italic text-powder-700">a person takes over.</span>
          </h1>
          <p className="lede max-w-prose">
            Cases that exhaust every escalation stage — or where you tell us the company is still
            stonewalling — get flagged for a consumer lawyer. Matching them to you is the next
            phase we&rsquo;re building.
          </p>
        </div>
        <div className="lg:justify-self-end">
          <Link to="/cases" className="btn-ghost">
            See flagged cases
            <ArrowRight className="w-4 h-4" strokeWidth={1.75} />
          </Link>
        </div>
      </header>

      <div className="grid sm:grid-cols-3 gap-4 mb-14">
        {[
          {
            icon: Scale,
            title: 'Consumer specialists',
            body: 'Advocates who file at District and State Commissions weekly, not occasionally.',
          },
          {
            icon: MapPin,
            title: 'Your jurisdiction',
            body: 'Matched to the Commission that actually has jurisdiction over your complaint.',
          },
          {
            icon: ShieldCheck,
            title: 'Your file, already built',
            body: 'They receive the complete case history Hakk assembled — every draft, deadline and document.',
          },
        ].map(({ icon: Icon, title, body }) => (
          <div key={title} className="card p-6">
            <div className="w-11 h-11 rounded-2xl bg-powder-100 grid place-items-center mb-4">
              <Icon className="w-[18px] h-[18px] text-powder-700" strokeWidth={1.5} />
            </div>
            <h2 className="text-lg mb-2">{title}</h2>
            <p className="text-sm text-ink-soft leading-relaxed">{body}</p>
          </div>
        ))}
      </div>

      {/* Placeholder roster, visibly inert */}
      <section>
        <p className="eyebrow mb-6">Preview of the matching screen</p>
        <div className="card divide-y divide-line-soft opacity-60 pointer-events-none select-none">
          {[
            ['Consumer disputes · e-commerce', 'Bengaluru', '11 yrs', 4.8],
            ['Banking & financial services', 'Mumbai', '8 yrs', 4.9],
            ['Telecom & utilities', 'New Delhi', '14 yrs', 4.7],
          ].map(([practice, city, years, rating], i) => (
            <div key={i} className="flex items-center gap-5 px-6 sm:px-8 py-6">
              <div className="w-12 h-12 rounded-2xl bg-canvas-sunk shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="h-4 w-40 rounded bg-canvas-sunk mb-2.5" />
                <p className="text-sm text-ink-muted">
                  {practice} &middot; {city} &middot; {years}
                </p>
              </div>
              <span className="inline-flex items-center gap-1.5 text-sm text-ink-muted shrink-0">
                <Star className="w-4 h-4" strokeWidth={1.75} />
                {rating}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
