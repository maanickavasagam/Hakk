# Hakk

An autonomous consumer-dispute resolution agent for India. Hakk takes a complaint
from a plain description to a filed, self-escalating case: it classifies the
dispute into the sector whose regulator actually governs it, drafts the complaint
in the right legal register citing the right statute, tracks every statutory
deadline, and escalates up the ladder on its own when one lapses.

> Hakk prepares and tracks consumer complaints. It is not a law firm and does not
> provide legal advice.

---

## Running it

Two processes. Backend first.

```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

Then open <http://localhost:5173>.

Fresh setup, if the checkout is clean:

```bash
python -m venv backend/.venv && backend/.venv/Scripts/python -m pip install -r backend/requirements.txt && npm --prefix frontend install
```

### Signing in

Phone + email, then a 6-digit code **emailed** to the address given at sign-up.
Configure SMTP in `backend/.env` and the code is sent for real, must be entered
exactly, expires in 10 minutes, is single-use, and is burned after 5 wrong
guesses:

```bash
# backend/.env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop   # Gmail app password, not the account password
SMTP_FROM_NAME=Hakk
```

Spaces in the app password are stripped automatically, since Google displays it
in four groups and everyone pastes it that way.

**Without SMTP configured the flow still works.** The code is printed to the
backend console and any well-formed 6-digit code is accepted, so the product
demos with no mail account at all:

```
==========================================================
  HAKK OTP  ->  9876543210   CODE: 482913
  (mock delivery: any 6-digit code is accepted)
==========================================================
```

If SMTP *is* configured but a send fails, it degrades to the console rather than
erroring — but the real code is then required, and the UI says where to find it.

First-time users are then asked to set a fallback password, which they can use
on later visits instead of waiting for a code.

---

## The demo clock

Statutory windows are real — 30 days for an e-commerce Grievance Officer, 30 days
before the RBI Ombudsman will admit a bank complaint. Those numbers are always
what the UI *displays*. For a live demo they are compressed onto a wall clock:

```
deadline_seconds = statutory_days × DEMO_SECONDS_PER_DAY
```

At the default of `2.0`, a 30-day window lapses in 60 seconds and a 15-day window
in 30 — relative proportions preserved. Change it live from the footer badge on
any screen, or via the API:

```bash
curl -X POST localhost:8000/api/config/clock \
  -H 'content-type: application/json' -d '{"seconds_per_day": 6}'
```

Set `seconds_per_day` to `86400` (or `DEMO_MODE=false`) for real time. Changing
the clock affects deadlines set *after* the change; a stage already counting down
keeps the deadline it was given.

---

## How a case moves

```
intake ──> classify ──┬──> active ──> (deadline lapses) ──> escalate ──> ... 
                      │                                          │
                      │                                          v
                      └──> unclassified                    lawyer_handoff
                           (contact + chat,                (ladder exhausted, or
                            never a dead end)               user marks non-responsive)
```

1. **Guided intake** — a fixed, ordered set of questions (not a chatbot). Answers
   are persisted step by step as structured JSON on the case.
2. **Documents** — uploads are read for text (PDF text layer, OCR for images,
   plain text) and parsed for order IDs, amounts, dates, UTRs. The user confirms
   or corrects every field before it is used. This is a **completeness check, not
   an authenticity check** — Hakk makes no fraud or forgery assessment, and says
   so in the UI.
3. **Classification** — structured answers plus confirmed document fields go to a
   Claude call with a strict JSON schema returning sector, confidence and
   reasoning. Below the confidence threshold (default 0.55) the user lands on a
   "couldn't confidently classify" screen with a real email, phone and chat box.
4. **Timeline** — the *entire* ladder for the matched sector is materialised
   immediately: every stage, its statutory window, the regulation it rests on,
   and the documents it will need. Nothing is sprung on the user later.
5. **Drafting** — a formal complaint for the current stage, citing the regulation
   attached to *that* stage. Always shown for review and edit; nothing is ever
   sent without an explicit approval.
6. **Escalation** — when a paid stage's deadline lapses, the scheduler drafts the
   next stage from the case history and advances the ladder, writing every step
   to the per-case activity log.

### Not waiting when there is nothing to wait for

Running the clock down only makes sense while the company is silent. Two other
things can happen, and both are handled:

- **They reject it, or reply without fixing it.** Recorded from the case page,
  this escalates *immediately* rather than burning the rest of the window — and
  that is what the regulations themselves say. RB-IOS 2026 cl. 10(1)(f) opens the
  Ombudsman once the complainant "is unsatisfied with the reply received", not
  only after 30 days of silence; Insurance Ombudsman Rules r. 14(3)(a)(i) and
  (iii) say the same; TCCR 2012 reg. 9 allows the appeal once redressal is
  unsatisfactory. Whatever the company actually said is stored and quoted back in
  the next letter.
- **They miss the acknowledgement window.** Where a rule imposes a short
  acknowledgement duty separate from redressal (48h under E-Commerce Rule 4(5),
  72h under TCCR reg. 13(1)(b)), missing it is recorded as a breach, notified,
  and pleaded at the next rung — but it deliberately does **not** shorten the
  redressal window, because no regulation says it does. Escalating early on an
  ack breach alone would put a legally wrong claim in a letter.

A third option, "they resolved it", closes the case instead of escalating it.

---

## Sector rules

One JSON file per sector in `backend/app/sector_rules/`. Each stage carries its
own deadline window and the regulation it is based on, so nothing is hardcoded to
a single statute — the drafter reads the citation off the stage row.

| Sector | Ladder | Primary basis |
|---|---|---|
| **E-commerce** | Grievance Officer (48h ack / 30d resolve) → Nodal Officer (Hakk checkpoint, no statutory SLA) → National Consumer Helpline (30d) → District Commission (e-Daakhil, 21d admissibility) | Consumer Protection Act 2019 ss.34,35,36(2),69; CP (E-Commerce) Rules 2020, Rules 4(5) and 4(1)(b) |
| **Banking & UPI** | Bank Grievance (30d wait) → RBI Ombudsman (CMS) → Appellate Authority (30d to appeal) | RB-Integrated Ombudsman Scheme 2026, cl. 10, 14, 17 |
| **Telecom** | Complaint Centre (3d) → Appellate Authority (39d disposal, 30d to file) → Consumer Commission / DoT | Telecom Consumers Complaint Redressal Regulations 2012, Regs 7–14 |
| **Insurance** | Written representation to the insurer (1 month) → Insurance Ombudsman (3-month award, ₹30 lakh cap, 1 year to file) → District Commission (e-Daakhil, 21d admissibility) | Insurance Ombudsman Rules 2017 (am. 2021), rr. 13, 14(3), 16, 17; CP Act 2019 ss.34,35,36(2),69 |
| **Airlines** | Airline Nodal Officer → Airline Appellate Authority → AirSewa (MoCA) → District Commission (e-Daakhil, 21d admissibility) | DGCA CAR Sec.3 Series M Part IV (Rev.4, 2023), paras 3.2.2, 3.3.2, 3.5.1, 3.9, 3.10.4; CP Act 2019 |

Adding a sector is a new JSON file — the loader, classifier schema and prompt,
timeline builder and drafter all read from it. No code change required: the
classifier's sector enum and the sector list in its system prompt are both built
from whatever JSON files are present.

Note the honesty convention carried through every file: where a ladder rung has
no statutory deadline (the airline Nodal Officer, the e-commerce Nodal Officer,
AirSewa, the RBI Ombudsman's own decision), `regulation_note` says so in as many
words and labels the number as Hakk's operational checkpoint. See
`backend/legal_sources/SOURCES.md` for what was verified against primary text and
what rests on secondary sources.

---

## LLM configuration

Classification and drafting try three paths in order, all producing the same
shape. Whichever answers is named in the UI (`via anthropic` / `via groq` /
`via template`) and stored on the row, so nothing implies a model wrote something
a template did.

```bash
# backend/.env — either, neither, or both
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
```

1. **Anthropic** — Claude Opus 5 with server-side structured outputs
   (`messages.parse` against a Pydantic schema), so sector and confidence come
   back already validated.
2. **Groq** — OpenAI-compatible JSON mode. There is no server-side schema
   enforcement, so the shape is spelled out in the prompt and the response is
   validated client-side against the same Pydantic model. Model defaults to
   `llama-3.3-70b-versatile`; override with `GROQ_CLASSIFIER_MODEL` /
   `GROQ_DRAFTER_MODEL`.
3. **Neither** — classification falls back to a transparent keyword scorer and
   drafting to a formal template. This is what the test suite exercises, and it
   is a supported configuration, not a degraded one.

`GET /api/config` reports `llm_provider` so you can see which is actually live.

### TLS interception

`app/config.py` injects [truststore](https://pypi.org/project/truststore/) at
import, before any SSL context exists, so Python uses the **OS** certificate
store rather than certifi's bundled list.

Without it, any machine running TLS-inspecting antivirus or a corporate proxy
(AVG, Zscaler, and friends re-sign every HTTPS connection with a private root)
fails every outbound API call with `CERTIFICATE_VERIFY_FAILED` — while `curl` and
the browser work fine, because they already trust that root through the OS. The
symptom looks like a bad API key and is not one.

---

## Payments

Mock only. `₹49` unlocks a single stage; the full bundle is `₹129–199` depending
on sector. Clicking Pay writes a `Payment` row and marks the stage unlocked
instantly — there is no gateway behind it, and the checkout says so.

Stage 1 is included; the user pays to unlock escalations.

---

## Layout

```
backend/
  app/
    config.py            demo clock, thresholds, paths, truststore injection
    db.py                engine, session, additive column catch-up
    models.py            SQLAlchemy models (+ iso() UTC serialiser)
    security.py          bcrypt + JWT
    routers/             auth, cases, documents, payments, meta
    services/
      rules.py           sector JSON loader
      extraction.py      PDF/OCR/text extraction + field parsing
      classifier.py      Anthropic -> Groq -> keyword classification
      drafter.py         Anthropic -> Groq -> template complaint generation
      mailer.py          SMTP OTP delivery (degrades to console)
      timeline.py        ladder construction, stage clocks, activity log
      scheduler.py       APScheduler deadline engine + shared escalation
    sector_rules/        ecommerce, banking, telecom, insurance, airlines .json
  legal_sources/         primary PDFs the rule files were verified against
frontend/
  tailwind.config.js     the shared design system (tokens -> CSS variables)
  index.html             pre-paint theme script
  src/
    index.css            palette variables, light + dark
    components/          Shell (nav, reminders, toasts), ui primitives
    lib/                 api client, auth context, theme
    pages/               SignIn, Landing, Cases, CaseDetail, NewComplaint, Lawyers
```

---

## Design system

Defined once in `frontend/tailwind.config.js` and `src/index.css`; every screen
inherits it.

- **Palette** — powder green (`#C8E6C9`–`#A5D6A7` core, extended to a full scale)
  used only for accents, active states and key CTAs. Base is warm off-white
  `#FAFAF8`, never pure white. Text is soft charcoal `#24261F`, never black.
  Status uses muted clay and rust rather than alarm colours.
- **Light and dark** — colours resolve through CSS variables declared once in
  `src/index.css`; `tailwind.config.js` reads them via
  `rgb(var(--token) / <alpha-value>)`. Because every screen already speaks in
  semantic tokens (`bg-canvas`, `text-ink`, `border-line`), the dark theme is a
  single block of re-pointed variables — there is not one `dark:` class anywhere
  in any page. Dark is a re-point, not an inversion: the base is a warm near-black
  carrying the same green undertone, and the powder/clay/rust scales are flipped
  end-for-end so that the `bg-powder-100` + `text-powder-900` pairing components
  already use stays legible instead of going white-on-white. Shadows deepen
  (`--shadow-boost`) rather than disappearing, so cards still lift.
- **Theme setting** — light / dark / **system**, cycled from the footer (and the
  top-right on the sign-in screen), persisted in `localStorage`. `system` is a
  real setting, not a default: it follows the OS live via `matchMedia`. An inline
  script in `index.html` applies the theme before first paint, so there is no
  flash of the wrong theme on load.
- **Type** — Fraunces (variable serif, soft optical axis) for headings, Inter for
  body, JetBrains Mono for references and countdowns.
- **Motion** — 150–250ms `cubic-bezier(0.32,0.72,0.28,1)` on hover and state;
  staggered fade-up on page entry; `prefers-reduced-motion` respected.
- **Depth** — soft, wide, low-opacity shadows so cards lift rather than box in.
- **Icons** — lucide-react throughout at 1.5–1.75 stroke.

---

## Tests

```bash
backend/.venv/Scripts/python tests/smoke.py
```

Drives the whole loop headlessly against a fresh database — auth, intake,
extraction, classification, timeline construction, drafting, payment, deadline
lapse, auto-escalation, the low-confidence path and lawyer handoff.

---

## Known limits

- OTP goes by **email**, not SMS, even though sign-in is keyed on the phone
  number. Without SMTP configured it falls back to the console and accepts any
  6-digit code.
- Payments are mocked; no gateway is connected.
- Approving a draft records it as filed — nothing is actually transmitted to any
  company or regulator.
- Image OCR needs a Tesseract binary on PATH. Without it, PDF text layers and
  plain text still extract, and users can enter fields manually.
- Lawyer matching is a stub; the handoff **flag** is real and set by the backend.
- The news feed is placeholder content shaped like a news-API response.
