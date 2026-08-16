# Legal source documents

Primary/near-primary government sources downloaded for grounding `sector_rules/*.json`.
All five rule files have now been written or rewritten against these sources — see
"Findings" below for what was verified against primary text, what rests on
secondary sources, and what is still uncited.

Retrieved: 2026-08-09 (e-commerce, banking, telecom), 2026-08-10 (insurance,
airlines). Re-check periodically — regulations amend.

## E-commerce

| File | Source | SHA-256 | Notes |
|---|---|---|---|
| `ecommerce/consumer_protection_act_2019.pdf` | [indiacode.nic.in](https://www.indiacode.nic.in/bitstream/123456789/16939/1/a2019-35.pdf) | `50120b13...` | Primary. Full Act, text layer, 39 pages. Act No. 35 of 2019. |
| `ecommerce/cp_ecommerce_rules_2020.pdf` | [thc.nic.in mirror](https://thc.nic.in/Central%20Governmental%20Rules/Consumer%20Protection%20(E-Commerce)%20Rules,%202020.pdf) | `54fed9f2...` | Primary text (scanned Gazette copy — **no text layer, needs OCR** before it's usable for search). Gazette of India, 23 July 2020. |
| `ecommerce/cp_ecommerce_rules_2020_icsi.pdf` | [ICSI](https://www.icsi.edu/media/webmodules/Consumer_Protection_E-Commerce_Rules_2020.pdf) | `7fa4541a...` | Secondary. Has a real text layer — used to verify Rule 4(5) and Rule 5(3) wording below since the primary scan can't be searched yet. |

## Banking

| File | Source | SHA-256 | Notes |
|---|---|---|---|
| `banking/rbi_ios_2026_scheme_sbi_mirror.pdf` | [SBI mirror of RBI notification](https://sbi.bank.in/documents/136/1364568/Reserve+Bank+Integrated+Ombudsman+Scheme+2026.pdf) | `f1195749...` | **Current scheme**, effective 1 July 2026. Mirrored via a regulated entity (SBI) because rbidocs.rbi.org.in blocks non-browser requests. |
| `banking/rbi_ios_2026_faq.pdf` | [rbi.org.in](https://www.rbi.org.in/commonman/Upload/English/FAQs/PDFs/RBIOS01072026.pdf) | `db923b0f...` | Official RBI FAQ, plain-language companion to the scheme above. |

**RB-IOS 2021 was NOT downloaded** — `rbidocs.rbi.org.in` served a bot-challenge page instead of the PDF. Not fetched because **it's superseded**: RB-IOS 2026 replaced it effective 2026-07-01, before today's date. `banking.json` currently cites the 2021 scheme and needs updating to 2026.

## Telecom

| File | Source | SHA-256 | Notes |
|---|---|---|---|
| `telecom/trai_tccr_2012.pdf` | [trai.gov.in](https://www.trai.gov.in/sites/default/files/2024-09/CA_05012012.pdf) | `5d0b0da1...` | Primary. Telecom Consumers Complaint Redressal Regulations, 2012 (as amended, per TRAI's own hosted copy). Text layer present, 13 pages. |
| `telecom/trai_consolidated_tcpr_2025.pdf` | [trai.gov.in](https://trai.gov.in/sites/default/files/2025-03/CR_TCPR_28032025.pdf) | `82bbfb29...` | **Different regulation, despite the similar name** — "Telecom Consumers Protection Regulations" covers SIM/data-deactivation rules, not complaint redressal. Kept for reference; do not use it as a source for the escalation ladder. |

## Insurance

| File | Source | Notes |
|---|---|---|
| `insurance/insurance_ombudsman_rules_2017_indiacode.pdf` | indiacode.nic.in | **Primary.** Insurance Ombudsman Rules, 2017 as amended to 18.5.2021 (G.S.R. 413(E) as amended by G.S.R. 785(E), G.S.R. 147(E) and G.S.R. 334(E)). Real text layer, 11 pages. This is the copy `insurance.json` was built against. |
| `insurance/insurance_ombudsman_rules_2017_cioins.pdf` | Council for Insurance Ombudsmen | Secondary, from the body that actually runs the scheme. Used to cross-check. |
| `insurance/irdai_faq_ombudsman_rules_2017.pdf` | IRDAI | Official plain-language FAQ. Independently confirms the one-month, one-year, three-month, ₹30 lakh and 30-day figures, and — importantly — that **no appeal lies against an Ombudsman award**. |

## Airlines

| File | Source | Notes |
|---|---|---|
| `airlines/dgca_car_sec3_seriesm_partiv.pdf` | dgca.gov.in | **Primary.** Civil Aviation Requirements, Section 3 (Air Transport), Series M Part IV, Rev. 4 dated 25 Jan 2023, effective 15 Feb 2023 — "Facilities to be provided to passengers by airlines due to denied boarding, cancellation of flights and delays in flights." Issued under Rule 133A of the Aircraft Rules, 1937. Real text layer, 8 pages. |

---

## Findings from checking `sector_rules/*.json` against these sources

Checked by full-text search inside each PDF (`pypdf` extraction), not just skimming.

### E-commerce — Stage 1 & 4 verified against primary text; Stages 2 & 3 had the same pattern of error as telecom/banking, now fixed (2026-08-09)
The first pass on this sector only checked 2 of 4 stages, and only against a secondary summary (ICSI), not the primary text — flagged as incomplete at the time. Redone properly:

- **Stage 1 (Grievance Officer, Rule 4(5)) — verified three ways**: the ICSI summary, an independent site (consumerprotection.in), and a general web search all quote the same "acknowledges... within forty-eight hours and redresses... within one month" language. No change needed.
- **Stage 4 (e-Daakhil) — verified word-for-word against the primary text** (`ecommerce/consumer_protection_act_2019.pdf`, real text layer, all 39 pages searched). Sections 34(1) (jurisdiction, ₹1 crore pecuniary limit — a detail not previously in the file), 35 (manner of filing), 36(2) ("the admissibility of the complaint shall ordinarily be decided within twenty-one days" — exact match), and 69(1)/(2) (two-year limitation, condonable) all confirmed exactly. `regulation` and `regulation_note` sharpened to cite Section 36(2) directly instead of just referencing it in passing.
- **Stage 2 (Nodal Officer) had the same structural error as telecom and banking.** The original citation, "Rule 5(3)", was wrong — cross-checking the ICSI text's surrounding context (the nodal-officer clause sits directly under the "Duties of E-commerce entities" heading, which is Rule 4's title) against an independent web search that named it explicitly ("Rule 4(1)(b) requires e-commerce entities to appoint a nodal person of contact...") points to **Rule 4(1)(b)**, not Rule 5(3). More importantly, the Rule's *stated purpose* for this appointment is "to ensure compliance with the provisions of the Act or the rules made thereunder" — a general compliance-liaison role, not a defined second-tier consumer-complaint handler with its own acknowledgment/resolution window the way the Grievance Officer explicitly has. Unlike telecom/banking, the stage was **kept** (there's a real appointment requirement and genuine practical value in escalating to it) but `deadline_days` is now explicitly labeled in `regulation_note` as Hakk's own checkpoint, not a statutory figure.
  - **Verification caveat**: the primary E-Commerce Rules PDF is a scanned, no-text-layer Gazette copy (see Known gaps), so this correction relies on triangulating 3 independent secondary sources rather than reading the primary text directly. They agree with each other, but this is a lower confidence level than the primary-sourced fixes elsewhere in this file. OCR would raise that to certain — flagged below, not done in this pass (would require installing a new OCR engine on the host machine, out of scope for a verification task without asking first).
- **Stage 3 (National Consumer Helpline) had no source at all before this pass.** Confirmed via search: 1915 toll-free (also WhatsApp/SMS at 8800001915), INGRAM = Integrated Grievance Redressal Mechanism, explicitly advisory/mediatory rather than adjudicatory (no power to pass a binding order). `deadline_days` changed from an unsourced 21 to **30**, matching NCH's actual stated operational expectation that a registered convergence-partner company responds to a forwarded complaint within 30 days — and `regulation_note` now says plainly this is an operational expectation, not a legal deadline, since NCH has no statute fixing one. `source_url` narrowed to the portal's own about page.

### Banking — was wrong year + a fabricated stage, now fixed (2026-08-09)
Full text of all 20 operative clauses was extracted page-by-page from `banking/rbi_ios_2026_scheme_sbi_mirror.pdf` and `banking.json` was rebuilt against it, not just relabeled:

- **Citation year corrected**: "Reserve Bank - Integrated Ombudsman Scheme, 2021" → **2026** (the 2021 scheme was repealed effective 2026-07-01, per Clause 20(1) of the 2026 text itself).
- **"Principal Nodal Officer Escalation" removed as a stage — same category of error as telecom's fabricated tier.** Clause 18(2) defines the Principal Nodal Officer as the *bank's own representative* in Ombudsman proceedings ("responsible for representing the Regulated Entity... in respect of complaints filed against the Regulated Entity"), not a consumer-facing escalation rung. Clause 10(1)(e)'s maintainability test only requires *any* written complaint to the bank — nothing requires it be addressed to a Nodal Officer specifically. The ladder is now 3 stages (Bank Grievance → RBI Ombudsman → Appellate Authority), not 4.
- **Stage 1 citation sharpened** to the exact sub-clauses: 10(1)(e) (must complain to the bank first, with proof), 10(1)(f) (30-day/no-reply-or-unsatisfied test), 10(1)(l) (Limitation Act window on the original complaint) — previously a vague "Clause 10(1)".
- **Stage 3 (Appellate Authority) now cites Clause 17(3) specifically** (complainant's 30-day appeal window, extendable 30 more days for sufficient cause) rather than a bare "Clause 17".
- **Stage 2 (RBI Ombudsman) `deadline_days` is explicitly flagged as an operational assumption, not a statutory figure** — checked the full text for any Ombudsman decision-timeline clause (`"ombudsman shall...within N days"`, `"shall dispose"`, etc.) and found none. Clause 14(1) states proceedings are deliberately "summary in nature," with only the bank's own 15-day response window (Clause 14(2)) fixed by the text. `regulation_note` says so explicitly rather than presenting the 30-day figure as if it were law.
- Removed an unverified secondary citation (a specific RBI circular number + "90 days" claim for unauthorised-transaction liability) that was never checked against a downloaded source — rather than carry an unverified figure forward under a "corrected" banner.
- `source_url` on all three stages updated to `https://cms.rbi.org.in/` (the Scheme's own designated filing portal, cited repeatedly in its text), replacing the generic `rbi.org.in` homepage.

### Telecom — was materially wrong, now fixed (2026-08-09)
The base regulation (TCCR 2012) did not contain the ladder `telecom.json` used to describe. Full text of every operative regulation (Regs 1–23) was extracted page-by-page from `telecom/trai_tccr_2012.pdf` and `telecom.json` was rebuilt against it:

- **"Nodal Officer" appears nowhere in the 2012 regulation.** The old Stage 2 ("Nodal Officer Escalation") was fabricated — there is no such tier. It has been removed; the ladder is now 3 stages (Complaint Centre → Appellate Authority → Consumer Commission/DoT), not 4.
- **Complaint resolution window is 3 days** (Reg 8(2), as amended by the Second Amendment Regulations 2013), not 7. `telecom.json` Stage 1 corrected.
- **The appeal must be filed within 30 days** of Stage 1's period expiring (condonable to 3 months for sufficient cause, Reg 9(3)) — this is a *filing* deadline, distinct from the *disposal* timeline. The disposal process is a defined sequence (Secretariat acknowledges in 3 days [Reg 13(1)(b)] → forwards to provider in 3 days, provider replies in 7 [Reg 13(1)(c)] → placed before Advisory Committee in 2 days [Reg 13(1)(d)] → Committee advises in 15 days [Reg 13(2)/9(6)] → placed before Appellate Authority in 2 days [Reg 13(3)] → Authority disposes in 10 days [Reg 14(2)]) totalling **39 days worst-case from the appeal reaching the Secretariat** — the old "39 days" figure turned out to be numerically right by coincidence, just attached to the wrong (nonexistent) stage. It's now Stage 2's `deadline_days`, with the 30-day filing window and 72-hour (3-day) acknowledgment noted in `regulation_note` / `ack_hours`.
- `source_url` on both regulated stages updated from the generic `trai.gov.in` homepage to the actual PDF: `https://www.trai.gov.in/sites/default/files/2024-09/CA_05012012.pdf`.

Stage 3 (Consumer Commission / DoT) was already correctly sourced to the Consumer Protection Act 2019 rather than TRAI's regulations, and needed no change beyond removing a stray "Nodal Officer" reference in its document list.

### Insurance — built from primary text (2026-08-10)
`insurance.json` was written against the full text of the amended Rules, not a summary. Every figure in it is quoted from a clause:

- **Stage 1 (30 days)** is Rule 14(3)(a)(ii)'s one-month silence period — the point at which the Ombudsman becomes reachable. `regulation_note` states plainly that a rejection (14(3)(a)(i)) or an unsatisfactory reply (14(3)(a)(iii)) opens that door *immediately*, without waiting the month out. This is the source of the app's early-escalation path.
- **Stage 2 (90 days)** is Rule 17(4)'s three-month award window ("shall finalise its findings and pass an award within a period of three months of the receipt of all requirements from the complainant"). Also captured: the one-year filing window (14(3)(b), condonable under 14(4)), the ₹30 lakh cap (17(3)(ii), "not award compensation exceeding rupees thirty lakhs (including relevant expenses, if any)"), the mediated-recommendation route (16(1), one month from mutual written consent), the insurer's 30-day compliance duty (17(6)), and the pending-elsewhere bar (14(5)).
- **Stage 3 is the Consumer Commission, not an appellate ombudsman tier — and this was checked rather than assumed.** The Rules contain no appeal against an award, and the IRDAI FAQ (Q14) confirms it: the award binds the insurer, and a dissatisfied complainant's recourse is "the normal process of law". Inventing an "Appellate Ombudsman" here would have repeated exactly the fabricated-tier error found in telecom and banking. `regulation_note` also flags the one-way bar in 14(5): going to a consumer forum first shuts the Ombudsman out, but not vice versa.

### Airlines — built from primary text, with the gaps labelled (2026-08-10)
`airlines.json` was written against the full CAR text. The honest headline: **the CAR fixes the compensation amounts precisely but fixes almost no deadlines.**

- **The amounts are exact and are quoted in Stage 1's `regulation_note`** so the drafter cites a figure instead of asking for goodwill: denied boarding at 200%/₹10,000 or 400%/₹20,000 (Para 3.2.2), cancellation at ₹5,000 / ₹7,500 / ₹10,000 by block time plus full refund (Para 3.3.2), involuntary downgrade at 75% domestic and 30/50/75% international by distance (Para 3.5.1). The force-majeure carve-outs (Paras 1.4, 1.5) and the no-contact-details carve-out (Para 3.3.3) are noted too, since they are the airline's standard defences.
- **Paras 3.10.4 requires a Nodal Officer and an Appellate Authority "in a stipulated time frame" but never states the time frame.** Stages 1 and 2 therefore carry Hakk checkpoints of 15 days each, explicitly labelled "not a statutory deadline" in `regulation_note`. Same for AirSewa at Stage 3 — Para 3.9.2 names the channel and fixes nothing.
- **Stage 4 rests on Para 3.9.3** ("liberty to complain to any statutory body/court set up under relevant applicable laws") read with the Consumer Protection Act 2019 sections already verified word-for-word for e-commerce Stage 4. The CAR creates the entitlement; it provides no forum that can enforce it.

### Still open
- Neither insurance nor airlines has an independent check on the *portal* half of its final stage (cioins.co.in complaint flow; airsewa.gov.in handling timelines) — same gap as e-commerce Stage 3 and telecom Stage 3.
- The DGCA CAR `source_url` points at DGCA's CAR index page rather than a stable direct PDF link, because the portal serves the document through a session-scoped viewer.
- No DoT public-grievance-portal source collected for `telecom.json` Stage 3 (Consumer Commission / DoT) — that stage's DoT-portal half is uncited; its Consumer Protection Act 2019 half is fine (verified below, under e-commerce Stage 4).
- The RBI circular on unauthorised electronic transaction liability (referenced, then removed, from `banking.json` Stage 1) hasn't been located/downloaded — if that liability-limiting detail is wanted back, it needs its own verified source rather than a from-memory citation.
- `ecommerce.json` Stage 2's "Rule 4(1)(b)" citation rests on triangulated secondary sources, not the primary text (see above) — would benefit from OCR confirmation if that becomes available.

---

## Known gaps

- E-commerce Rules 2020 primary copy is a scanned PDF with no text layer — needs OCR (the app's own `pytesseract` pipeline can do this) before it can be used for automated clause extraction/RAG.
- RB-IOS 2021 (superseded) was not obtainable — not a blocker since 2026 is now current, but means no direct diff between the two versions.
- No National Consumer Helpline (NCH/INGRAM) or e-Daakhil source document collected yet — `ecommerce.json` Stage 3/4 haven't been checked against anything primary.
- No DoT public-grievance-portal source collected for `telecom.json` Stage 4.
