"""Headless end-to-end smoke test of the Hakk backend."""
import io
import os
import pathlib
import sys
import time

BACKEND = pathlib.Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

# Run against a throwaway database so a live dev server's data is untouched.
db = BACKEND / "hakk_test.db"
if db.exists():
    db.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{db}"

# Force the console/mock OTP path. Without this the suite mails a live code to
# its own fake address on every run — load_dotenv() does not override variables
# that are already set, so blanking these here wins over backend/.env.
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASSWORD"] = ""

from fastapi.testclient import TestClient
from app.main import app
from app.services import drafter

FAIL = []


def check(label, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'}  {label}  {extra}")
    if not cond:
        FAIL.append(label)


# --- regression test: additive migration must handle NOT-NULL boolean columns
# on tables that already have rows. SQLite's ALTER TABLE ADD COLUMN rejects a
# NOT NULL column with nothing to backfill existing rows with — CREATE TABLE
# never hits this (a fresh table has no rows), so this bug only ever showed up
# against a real, already-populated hakk.db, never in a from-scratch test run.
# Caught once by hand when notifications.emailed was added; pinned here so it
# can't regress silently the next time a NOT NULL column is added to a model.
def _test_additive_migration_backfills_not_null_default() -> None:
    import sqlite3
    import tempfile

    from sqlalchemy import Boolean, Column, Integer, MetaData, Table, create_engine, text

    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "migration_test.db"
        engine = create_engine(f"sqlite:///{path}")

        # Simulate an "old" deployment: create the table without the column
        # a later model version adds, then insert rows — the exact shape a
        # real user's hakk.db was in before notifications.emailed existed.
        old_meta = MetaData()
        Table("widgets", old_meta, Column("id", Integer, primary_key=True))
        old_meta.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO widgets DEFAULT VALUES"))

        # Point db.py's migration helper at metadata that has the new NOT
        # NULL boolean column, the same shape as Notification.emailed.
        from app import db as db_module

        new_meta = MetaData()
        Table(
            "widgets",
            new_meta,
            Column("id", Integer, primary_key=True),
            Column("flag", Boolean, nullable=False, default=False),
        )

        original_engine, original_base = db_module.engine, db_module.Base
        db_module.engine = engine
        db_module.Base = type("TempBase", (), {"metadata": new_meta})
        try:
            db_module._add_missing_columns()
        finally:
            db_module.engine, db_module.Base = original_engine, original_base

        raw = sqlite3.connect(str(path))
        try:
            cols = {r[1] for r in raw.execute("pragma table_info(widgets)")}
            check("migration adds a NOT NULL column to a non-empty table without crashing", "flag" in cols)
            rows = raw.execute("select flag from widgets").fetchall()
            check(
                "existing rows are backfilled to the model's Python-side default, not left NULL",
                bool(rows) and all(r[0] == 0 for r in rows),
                rows,
            )
        finally:
            raw.close()
            # Windows keeps the SQLite file locked until every handle on it is
            # released — without this the TemporaryDirectory cleanup below
            # fails with a PermissionError on exit, masking a passing test as
            # a crash.
            engine.dispose()


_test_additive_migration_backfills_not_null_default()


with TestClient(app) as c:
    # speed the demo clock way up for the test
    r = c.post("/api/config/clock", json={"seconds_per_day": 0.15, "enabled": True})
    check("clock configurable", r.status_code == 200, r.json())

    # --- auth ---
    r = c.post("/api/auth/start", json={"phone": "9876543210", "email": "a@b.com", "full_name": "Asha Menon"})
    check("otp start", r.status_code == 200 and r.json()["sent"])
    check("no SMTP configured -> console delivery, no mail sent", r.json()["delivery"] == "console", r.json()["delivery"])

    r = c.post("/api/auth/verify", json={"phone": "9876543210", "code": "123456"})
    check("otp verify (any 6 digits, console mode)", r.status_code == 200, r.status_code)
    tok = r.json()["token"]
    check("needs password setup", r.json()["needs_password_setup"] is True)
    H = {"Authorization": f"Bearer {tok}"}

    r = c.post("/api/auth/password", json={"password": "hunter2hunter2"}, headers=H)
    check("set fallback password", r.status_code == 200, r.status_code)

    r = c.post("/api/auth/login", json={"phone": "9876543210", "password": "hunter2hunter2"})
    check("password login", r.status_code == 200, r.status_code)

    r = c.post("/api/auth/login", json={"phone": "9876543210", "password": "wrong-password"})
    check("bad password rejected", r.status_code == 401)

    # --- intake ---
    r = c.get("/api/cases/intake/questions")
    check("intake questions", r.status_code == 200 and r.json()["total_steps"] == 5)

    r = c.post("/api/cases", json={"title": "Undelivered order"}, headers=H)
    check("create case", r.status_code == 201, r.status_code)
    cid = r.json()["id"]

    # classify before answering -> should 400
    r = c.post(f"/api/cases/{cid}/classify", headers=H)
    check("classify blocked until required answers", r.status_code == 400)

    answers = {
        "what_happened": "Paid but never received the product or service",
        "what_happened_detail": "I ordered wireless headphones on Flipkart for Rs 2500 on 14 March. Tracking showed delivered but the parcel never arrived. Refund was refused.",
        "company": "Flipkart",
        "reference_number": "OD4521987",
        "amount_involved": "2500",
        "when_it_happened": "2026-03-14",
        "desired_resolution": "A full refund of the amount paid",
        "prior_contact": "Yes, multiple times through several channels",
        "prior_contact_detail": "Ticket 4471 raised, no response in 3 weeks.",
    }
    r = c.patch(f"/api/cases/{cid}/answers", json={"answers": answers}, headers=H)
    check("answers stored", r.status_code == 200 and r.json()["answers"]["company"] == "Flipkart")

    # --- document upload + extraction ---
    invoice = (
        "TAX INVOICE\nFlipkart Internet Pvt Ltd\n"
        "Order ID: OD4521987\nInvoice No: INV-88213\n"
        "Transaction ID: UTR402318774512\n"
        "Date: 14/03/2026\nItem: Wireless Headphones\n"
        "Total: Rs 2500.00\nAmount: Rs 2500.00\n"
        "Mobile: 9876543210\nEmail: asha@example.com\n"
    ).encode()
    r = c.post(
        f"/api/cases/{cid}/documents",
        files={"file": ("invoice.txt", io.BytesIO(invoice), "text/plain")},
        headers=H,
    )
    check("upload + extract", r.status_code == 201, r.status_code)
    doc = r.json()
    keys = [f["key"] for f in doc["fields"]]
    check("extracted order id", "order_id" in keys, keys)
    check("extracted amount", "amount" in keys or "total" in keys, keys)
    check("completeness disclaimer present", "not a fraud" in doc["disclaimer"].lower())

    fields = doc["fields"]
    for f in fields:
        if f["key"] == "order_id":
            f["value"] = "OD4521987"  # user confirms
    r = c.post(f"/api/cases/{cid}/documents/{doc['id']}/confirm", json={"fields": fields}, headers=H)
    check("confirm extracted fields", r.status_code == 200 and r.json()["is_confirmed"])

    # --- classification ---
    r = c.post(f"/api/cases/{cid}/classify", headers=H)
    check("classify", r.status_code == 200, r.status_code)
    body = r.json()
    check("classified confidently", body["classified"] is True, body.get("reasoning"))
    case = body["case"]
    check("sector = ecommerce", case["sector"] == "ecommerce", case["sector"])
    check("timeline built upfront", len(case["stages"]) == 4, len(case["stages"]))
    check("stage 1 draft exists", len(case["drafts"]) == 1)

    d0 = case["drafts"][0]
    check("draft cites E-Commerce Rules", "E-Commerce" in d0["legal_basis"], d0["legal_basis"])
    check("draft has body", len(d0["body"]) > 400, len(d0["body"]))
    print("\n----- STAGE 1 DRAFT (first 700 chars) -----")
    print(d0["body"][:700])
    print("----- end -----\n")

    st = case["stages"]
    check("stage1 paid/included", st[0]["paid"] is True)
    check("stage2 locked", st[1]["paid"] is False and st[1]["status"] == "locked")
    check("stages show real statutory days", st[0]["deadline_days"] == 30, st[0]["deadline_days"])
    check("required docs listed upfront", len(st[0]["required_documents"]) >= 3)
    check("nodal officer cites Rule 4(1)(b), not the wrong 5(3)", "4(1)(b)" in st[1]["regulation"], st[1]["regulation"])
    check("final stage is e-Daakhil", st[3]["key"] == "edaakhil", st[3]["key"])
    check("e-Daakhil cites Sections 34, 35, 36(2), 69", all(s in st[3]["regulation"] for s in ["34", "35", "36(2)", "69"]), st[3]["regulation"])
    check("e-Daakhil note quotes the verified 21-day admissibility language", "twenty-one days" in st[3]["regulation_note"], st[3]["regulation_note"])

    # --- draft edit + approve ---
    r = c.patch(f"/api/cases/{cid}/drafts/{d0['id']}", json={"body": d0["body"] + "\n\n[edited by user]"}, headers=H)
    check("edit draft", r.status_code == 200 and "[edited by user]" in r.json()["body"])
    r = c.post(f"/api/cases/{cid}/drafts/{d0['id']}/approve", headers=H)
    check("approve draft", r.status_code == 200 and r.json()["draft"]["status"] == "approved")

    # --- payment for stage 2 ---
    r = c.get(f"/api/cases/{cid}/payments/options", headers=H)
    check("payment options", r.status_code == 200 and r.json()["mock"] is True)
    opts = r.json()
    check("single stage price 4900", opts["single"][0]["price_paise"] == 4900)
    check("bundle offered", opts["bundle"]["price_paise"] == 14900, opts["bundle"])

    stage2_id = st[1]["id"]
    r = c.post(f"/api/cases/{cid}/payments", json={"kind": "single", "stage_id": stage2_id}, headers=H)
    check("mock pay stage 2", r.status_code == 201 and r.json()["ok"], r.status_code)

    # --- let the deadline lapse and watch auto-escalation ---
    print("\nwaiting for stage 1 deadline to lapse (compressed clock)...")
    escalated = False
    for _ in range(60):
        time.sleep(1)
        r = c.get(f"/api/cases/{cid}/activity", headers=H)
        j = r.json()
        if j["current_stage_index"] == 1:
            escalated = True
            break
    check("auto-escalated to stage 2", escalated, f"current_stage_index={j['current_stage_index']}")

    events = [a["event"] for a in j["activity"]]
    check("lapse logged", any("lapsed" in e for e in events), events[:6])
    check("auto-escalation logged", any("Auto-escalated" in e for e in events), events[:6])
    check("agent-authored activity", any(a["actor"] == "agent" for a in j["activity"]))
    check("stage 2 draft auto-generated", len(j["drafts"]) == 2, len(j["drafts"]))

    d1 = j["drafts"][-1]
    check("stage 2 draft is auto", d1["auto_generated"] is True)
    check("auto-escalated draft cites Rule 4(1)(b), not the wrong 5(3)", "4(1)(b)" in d1["legal_basis"], d1["legal_basis"])
    check("escalation draft is substantive", len(d1["body"]) > 400, len(d1["body"]))

    print("\n----- ACTIVITY LOG -----")
    for a in reversed(j["activity"]):
        print(f"  [{a['actor']:6}] {a['event']}")
    print("----- end -----\n")

    r = c.get("/api/notifications", headers=H)
    notes = r.json()["notifications"]
    kinds = [n["kind"].split(":")[0] for n in notes]
    check("reminders raised", "lapsed" in kinds, kinds)
    check("notifications report email-delivery state", all("emailed" in n for n in notes), notes[:1])
    check(
        "no SMTP configured in this suite -> nothing claims to have been emailed",
        all(n["emailed"] is False for n in notes),
        [n["emailed"] for n in notes],
    )

    # --- unclassifiable path ---
    r = c.post("/api/cases", json={"title": "Odd one"}, headers=H)
    cid2 = r.json()["id"]
    c.patch(f"/api/cases/{cid2}/answers", json={"answers": {
        "what_happened": "Something else",
        "what_happened_detail": "A general issue occurred and nobody helped me.",
        "company": "Zzyzx Trust",
        "when_it_happened": "2026-05-01",
        "desired_resolution": "A written apology and confirmation of correction",
        "prior_contact": "No, not yet",
    }}, headers=H)
    r = c.post(f"/api/cases/{cid2}/classify", headers=H)
    check("low confidence -> not classified", r.json()["classified"] is False, r.json().get("confidence"))
    check("contact shown, not a dead end", "email" in r.json()["contact"])

    r = c.post("/api/support/chat", json={"message": "I need a lawyer"})
    check("support chatbot replies", r.status_code == 200 and len(r.json()["reply"]) > 20)

    # --- lawyer handoff ---
    r = c.post(f"/api/cases/{cid}/mark-unresponsive", headers=H)
    check("manual lawyer handoff", r.json()["lawyer_handoff"] is True and r.json()["status"] == "lawyer_handoff")

    r = c.get("/api/news")
    check("news cards in news-API shape", len(r.json()["articles"]) == 5 and "source" in r.json()["articles"][0])

    # --- telecom ladder (rebuilt against the real TCCR 2012 text) ---
    r = c.post("/api/cases", json={"title": "Airtel billing dispute"}, headers=H)
    cid3 = r.json()["id"]
    c.patch(f"/api/cases/{cid3}/answers", json={"answers": {
        "what_happened": "Wrongly billed or overcharged",
        "what_happened_detail": "My Airtel postpaid bill charged Rs 1800 for a data pack I never activated. Network signal has also been dropping calls for two weeks.",
        "company": "Airtel",
        "reference_number": "AT-88213",
        "amount_involved": "1800",
        "when_it_happened": "2026-04-01",
        "desired_resolution": "A corrected bill",
        "prior_contact": "Yes, by phone to customer care",
    }}, headers=H)
    r = c.post(f"/api/cases/{cid3}/classify", headers=H)
    body3 = r.json()
    check("telecom classified", body3.get("classified") is True and body3["case"]["sector"] == "telecom", body3.get("case", {}).get("sector"))
    st3 = body3["case"]["stages"]
    check("telecom ladder has 3 stages (no fabricated Nodal Officer tier)", len(st3) == 3, [s["key"] for s in st3])
    check("stage 1 = 3-day Complaint Centre window (Reg 8(2))", st3[0]["deadline_days"] == 3, st3[0]["deadline_days"])
    check("stage 2 = Appellate Authority, 39-day disposal (Reg 9-14)", st3[1]["key"] == "appellate_authority" and st3[1]["deadline_days"] == 39, st3[1])
    check("stage 2 cites Regulations 9 to 14", "9 to 14" in st3[1]["regulation"], st3[1]["regulation"])
    check("stage 3 unchanged: Consumer Commission / DoT on CPA 2019", st3[2]["key"] == "commission_and_dot", st3[2]["key"])
    d3 = body3["case"]["drafts"][0]
    check("telecom draft cites Reg 7/8(2), not a Nodal Officer", "7 and 8(2)" in d3["legal_basis"] and "Nodal" not in d3["body"], d3["legal_basis"])

    # --- banking ladder (rebuilt against the real RB-IOS 2026 text) ---
    r = c.post("/api/cases", json={"title": "HDFC unauthorised debit"}, headers=H)
    cid4 = r.json()["id"]
    c.patch(f"/api/cases/{cid4}/answers", json={"answers": {
        "what_happened": "Unauthorised or unrecognised charge",
        "what_happened_detail": "An unauthorised UPI transaction of Rs 15000 was debited from my HDFC Bank account. I never authorised this payment and reported it to the bank immediately.",
        "company": "HDFC Bank",
        "reference_number": "UTR998877665544",
        "amount_involved": "15000",
        "when_it_happened": "2026-05-10",
        "desired_resolution": "Reversal of the wrongful charge",
        "prior_contact": "Yes, by phone to customer care",
    }}, headers=H)
    r = c.post(f"/api/cases/{cid4}/classify", headers=H)
    body4 = r.json()
    check("banking classified", body4.get("classified") is True and body4["case"]["sector"] == "banking", body4.get("case", {}).get("sector"))
    st4 = body4["case"]["stages"]
    check("banking ladder has 3 stages (no fabricated Nodal Officer tier)", len(st4) == 3, [s["key"] for s in st4])
    check("primary_statute is RB-IOS 2026, not 2021", "2026" in body4["case"]["primary_statute"], body4["case"]["primary_statute"])
    check("stage 1 = 30-day bank grievance window (Clause 10(1))", st4[0]["deadline_days"] == 30, st4[0]["deadline_days"])
    check("stage 2 = RBI Ombudsman, no nodal_officer key present", st4[1]["key"] == "rbi_ombudsman", [s["key"] for s in st4])
    check("stage 3 = Appellate Authority, 30 days (Clause 17(3))", st4[2]["key"] == "appellate_authority" and st4[2]["deadline_days"] == 30, st4[2])
    check("stage 3 cites Clause 17(3)", "17(3)" in st4[2]["regulation"], st4[2]["regulation"])
    d4 = body4["case"]["drafts"][0]
    check("banking draft cites RB-IOS 2026, not a Nodal Officer", "2026" in d4["legal_basis"] and "Nodal" not in d4["body"], d4["legal_basis"])

    # --- insurance ladder (built against the Insurance Ombudsman Rules 2017) ---
    r = c.post("/api/cases", json={"title": "Star Health claim rejected"}, headers=H)
    cid5 = r.json()["id"]
    c.patch(f"/api/cases/{cid5}/answers", json={"answers": {
        "what_happened": "Something else",
        "what_happened_detail": "Star Health repudiated my mediclaim of Rs 180000 for a hospitalisation, calling it a pre-existing disease, although the policy has run continuously for four years and the condition was disclosed in the proposal form.",
        "company": "Star Health Insurance",
        "reference_number": "CLM-77120",
        "amount_involved": "180000",
        "when_it_happened": "2026-06-02",
        "desired_resolution": "A full refund of the amount paid",
        "prior_contact": "Yes, by email",
    }}, headers=H)
    r = c.post(f"/api/cases/{cid5}/classify", headers=H)
    body5 = r.json()
    check("insurance classified", body5.get("classified") is True and body5["case"]["sector"] == "insurance", body5.get("case", {}).get("sector"))
    st5 = body5["case"]["stages"]
    check("insurance ladder has 3 stages", len(st5) == 3, [s["key"] for s in st5])
    check("primary_statute is the Insurance Ombudsman Rules 2017", "Insurance Ombudsman Rules, 2017" in body5["case"]["primary_statute"], body5["case"]["primary_statute"])
    check("stage 1 = 30-day insurer reply window (Rule 14(3)(a))", st5[0]["deadline_days"] == 30 and "14(3)(a)" in st5[0]["regulation"], st5[0]["regulation"])
    check("stage 2 = Ombudsman, 90-day award window (Rule 17(4))", st5[1]["key"] == "insurance_ombudsman" and st5[1]["deadline_days"] == 90, st5[1]["deadline_days"])
    check("stage 2 note carries the verified Rs 30 lakh cap", "30 lakh" in st5[1]["regulation_note"], "cap missing")
    check("stage 2 note carries the verified one-year filing window", "within one year" in st5[1]["regulation_note"], "filing window missing")
    check("stage 3 = Commission, no fabricated appeal to an Ombudsman appellate tier", st5[2]["key"] == "consumer_commission", st5[2]["key"])
    check("stage 3 states there is no appeal against the award", "no appeal" in st5[2]["regulation_note"].lower(), st5[2]["regulation_note"][:80])
    d5 = body5["case"]["drafts"][0]
    check("insurance draft cites the Ombudsman Rules", "Insurance Ombudsman Rules, 2017" in d5["legal_basis"], d5["legal_basis"])

    # --- airlines ladder (built against DGCA CAR Sec 3 Series M Part IV) ---
    r = c.post("/api/cases", json={"title": "IndiGo cancellation"}, headers=H)
    cid6 = r.json()["id"]
    c.patch(f"/api/cases/{cid6}/answers", json={"answers": {
        "what_happened": "Something else",
        "what_happened_detail": "IndiGo cancelled flight 6E-2134 from Bengaluru to Delhi four hours before departure. No alternate flight was arranged and only a travel voucher was offered instead of the refund and compensation I am entitled to.",
        "company": "IndiGo",
        "reference_number": "PNR-K4T9XZ",
        "amount_involved": "7400",
        "when_it_happened": "2026-07-14",
        "desired_resolution": "A full refund of the amount paid",
        "prior_contact": "Yes, through their app or website chat",
    }}, headers=H)
    r = c.post(f"/api/cases/{cid6}/classify", headers=H)
    body6 = r.json()
    check("airlines classified", body6.get("classified") is True and body6["case"]["sector"] == "airlines", body6.get("case", {}).get("sector"))
    st6 = body6["case"]["stages"]
    check("airlines ladder has 4 stages", len(st6) == 4, [s["key"] for s in st6])
    check("stage 1 = airline Nodal Officer (Paras 3.9.1, 3.10.4)", st6[0]["key"] == "airline_nodal_officer" and "3.10.4" in st6[0]["regulation"], st6[0]["regulation"])
    check("stage 1 note carries the verified cancellation compensation figures", all(v in st6[0]["regulation_note"] for v in ["5,000", "7,500", "10,000"]), "figures missing")
    check("stage 1 note flags the checkpoint as non-statutory", "not a statutory deadline" in st6[0]["regulation_note"], "honesty note missing")
    check("stage 2 = airline Appellate Authority", st6[1]["key"] == "airline_appellate_authority", st6[1]["key"])
    check("stage 3 = AirSewa (Para 3.9.2)", st6[2]["key"] == "air_sewa" and "3.9.2" in st6[2]["regulation"], st6[2]["regulation"])
    check("stage 4 = Commission on CPA 2019 read with Para 3.9.3", st6[3]["key"] == "consumer_commission" and "3.9.3" in st6[3]["regulation"], st6[3]["regulation"])
    d6 = body6["case"]["drafts"][0]
    check("airlines draft cites the DGCA CAR", "CAR" in d6["legal_basis"], d6["legal_basis"])

    # --- escalation carries the case history forward ------------------------
    # Asserted against the deterministic parts of the drafter rather than the
    # prose of a returned letter: an LLM says "my earlier complaint to the
    # Grievance Officer" one run and "the initial grievance" the next, so a
    # keyword match on generated prose fails at random while nothing is wrong.
    # What must hold is that the history reaches the model at all, and that the
    # no-API-key path states it outright.
    esc_ctx = {
        "stage": {
            "index": 1, "name": "Nodal Officer Escalation",
            "authority": "Nodal Person of Contact",
            "regulation": "Consumer Protection (E-Commerce) Rules, 2020 - Rule 4(1)(b)",
            "regulation_note": "Rule 4(1)(b) requires a nodal person of contact.",
            "deadline_days": 15, "ack_hours": None,
        },
        "answers": {"what_happened_detail": "Ordered headphones, never delivered."},
        "documents": [], "company": "Flipkart", "user_name": "Asha Menon",
        "user_email": "a@b.com", "user_phone": "9876543210",
        "next_stage_name": "National Consumer Helpline",
        "history": [{
            "index": 0, "name": "Grievance Officer Complaint",
            "authority": "Company Grievance Officer",
            "outcome": "the 30-day window under Rule 4(5) expired without a substantive response",
        }],
    }
    prompt = drafter._build_prompt(esc_ctx)
    check("history is put in front of the drafter", "<case_history>" in prompt and "Grievance Officer Complaint" in prompt)
    check("drafter is told this is an escalation", "This is an escalation" in prompt)
    tmpl = drafter._template_draft(esc_ctx)
    check("template escalation names the earlier stage", "Grievance Officer Complaint" in tmpl and "expired" in tmpl, tmpl[:80])

    # --- rejection escalates immediately, without waiting out the clock -----
    r = c.post("/api/cases", json={"title": "Refund refused"}, headers=H)
    cid7 = r.json()["id"]
    c.patch(f"/api/cases/{cid7}/answers", json={"answers": {
        "what_happened": "Refund promised but not credited",
        "what_happened_detail": "I returned wireless headphones to Flipkart three weeks ago and the pickup was completed, but the refund of Rs 2500 has still not been credited to my account.",
        "company": "Flipkart",
        "when_it_happened": "2026-07-01",
        "desired_resolution": "A full refund of the amount paid",
        "prior_contact": "Yes, by email",
    }}, headers=H)
    case7 = c.post(f"/api/cases/{cid7}/classify", headers=H).json()["case"]
    st7 = case7["stages"]
    check("ack window scheduled where the rule imposes one", st7[0]["ack_hours"] == 48 and st7[0]["ack_deadline_at"], st7[0]["ack_deadline_at"])
    c.post(f"/api/cases/{cid7}/payments", json={"kind": "single", "stage_id": st7[1]["id"]}, headers=H)

    r = c.post(f"/api/cases/{cid7}/stages/{st7[0]['id']}/acknowledge", json={"reference": "TKT-9910"}, headers=H)
    check("acknowledgement recorded", r.status_code == 200 and r.json()["stages"][0]["acknowledged_at"], r.status_code)
    check("acknowledging does not advance the ladder", r.json()["current_stage_index"] == 0, r.json()["current_stage_index"])

    r = c.post(f"/api/cases/{cid7}/stages/{st7[0]['id']}/response",
               json={"outcome": "rejected", "note": "Refund denied: return window closed."}, headers=H)
    check("rejection accepted", r.status_code == 200, r.status_code)
    j7 = r.json()
    check("rejection escalates immediately, no timeout wait", j7["current_stage_index"] == 1, j7["current_stage_index"])
    check("rejected stage records its outcome", j7["stages"][0]["outcome"] == "rejected", j7["stages"][0]["outcome"])
    check("company's own words retained for the next draft", "return window closed" in j7["stages"][0]["outcome_note"], j7["stages"][0]["outcome_note"])
    check("next draft generated on rejection", len(j7["drafts"]) == 2, len(j7["drafts"]))
    check("early escalation logged", any("closed early" in a["event"] for a in j7["activity"]), [a["event"] for a in j7["activity"]][:4])
    r = c.post(f"/api/cases/{cid7}/stages/{st7[0]['id']}/response", json={"outcome": "rejected"}, headers=H)
    check("a stage cannot be closed twice", r.status_code == 400, r.status_code)

    # resolved closes the case rather than escalating it
    r = c.post("/api/cases", json={"title": "Resolved case"}, headers=H)
    cid8 = r.json()["id"]
    c.patch(f"/api/cases/{cid8}/answers", json={"answers": {
        "what_happened": "Refund promised but not credited",
        "what_happened_detail": "Flipkart order OD1 was returned and the refund of Rs 900 was not credited for two weeks.",
        "company": "Flipkart", "when_it_happened": "2026-07-05",
        "desired_resolution": "A full refund of the amount paid", "prior_contact": "Yes, by email",
    }}, headers=H)
    case8 = c.post(f"/api/cases/{cid8}/classify", headers=H).json()["case"]
    r = c.post(f"/api/cases/{cid8}/stages/{case8['stages'][0]['id']}/response",
               json={"outcome": "resolved", "note": "Refund credited on 12 July."}, headers=H)
    check("resolved closes the case instead of escalating", r.json()["status"] == "resolved", r.json()["status"])
    check("resolved stage marked completed", r.json()["stages"][0]["status"] == "completed", r.json()["stages"][0]["status"])

    # --- free-text intake: extraction feeds the exact same pipeline ---------
    r = c.post("/api/cases", json={"title": None}, headers=H)
    cid9 = r.json()["id"]
    r = c.post(
        f"/api/cases/{cid9}/intake/extract",
        json={
            "text": "On 14 March I ordered a pair of headphones from Flipkart for Rs 2500. "
            "They were never delivered even though tracking showed complete. I emailed "
            "support twice, they said wait 48 hours, never heard back. I want a full refund."
        },
        headers=H,
    )
    # Extraction depends on a live LLM quota (Groq's free tier is 100k tokens/day
    # and this suite shares it with manual testing), so a 502 here can be
    # "no quota left right now" rather than a real bug. Either a clean success or
    # a graceful, documented failure is acceptable; a 500 or a crash is not.
    check("extraction either succeeds or fails gracefully (never a 500)", r.status_code in (200, 502, 503), r.status_code)
    extracted = r.json() if r.status_code == 200 else None

    if extracted is not None:
        check("extraction understood the complaint", extracted["understood"] is True)
        check(
            "extraction filled the closed-option fields from the same list the guided form uses",
            extracted["answers"]["what_happened"] == "Paid but never received the product or service",
            extracted["answers"].get("what_happened"),
        )
        check("extraction pulled the company", extracted["answers"].get("company") == "Flipkart", extracted["answers"].get("company"))
        check("extraction pulled the amount", extracted["answers"].get("amount_involved") == "2500", extracted["answers"].get("amount_involved"))
        check(
            "extracted date resolves against the real year, not the model's training cutoff",
            str(extracted["answers"].get("when_it_happened", "")).startswith("2026"),
            extracted["answers"].get("when_it_happened"),
        )

        # The extracted answers are not saved by the endpoint itself — confirm
        # they only take effect once PATCHed, exactly like a guided-form answer.
        r = c.get(f"/api/cases/{cid9}", headers=H)
        check("extraction endpoint does not itself save anything", r.json()["answers"] == {}, r.json()["answers"])

        r = c.patch(f"/api/cases/{cid9}/answers", json={"answers": extracted["answers"]}, headers=H)
        check("extracted answers save through the normal answers endpoint, unchanged", r.status_code == 200, r.status_code)
        r = c.post(f"/api/cases/{cid9}/classify", headers=H)
        body9 = r.json()
        check("case built from free text classifies normally", body9.get("classified") is True and body9["case"]["sector"] == "ecommerce", body9.get("case", {}).get("sector"))
        check("stage 1 draft exists for the free-text case", len(body9["case"]["drafts"]) == 1)
    else:
        print(f"  (skipped: extraction unavailable right now — {r.json().get('detail')})")

    r = c.post(f"/api/cases/{cid9}/intake/extract", json={"text": ""}, headers=H)
    check("empty text rejected before hitting the model", r.status_code == 422, r.status_code)

    # Out-of-scope text is 'understood' as a complaint but is not a Hakk sector —
    # that judgment belongs to classify(), not to extraction. It should NOT be
    # silently forced into ecommerce/banking/telecom/insurance/airlines here.
    r = c.post("/api/cases", json={"title": None}, headers=H)
    cid10 = r.json()["id"]
    r = c.post(
        f"/api/cases/{cid10}/intake/extract",
        json={
            "text": "My landlord in Pune refuses to return my Rs 50000 security deposit even "
            "though I vacated the flat two months ago in perfect condition."
        },
        headers=H,
    )
    out_of_scope = r.json() if r.status_code == 200 else None

    if out_of_scope is not None:
        check("out-of-scope text is still 'understood' as a complaint", out_of_scope["understood"] is True, out_of_scope)
        c.patch(f"/api/cases/{cid10}/answers", json={"answers": {**out_of_scope["answers"], "company": "Landlord"}}, headers=H)
        r = c.post(f"/api/cases/{cid10}/classify", headers=H)
        body10 = r.json()
        check(
            "out-of-scope complaint routes through the EXISTING low-confidence path — no new dead end introduced",
            body10.get("classified") is False and body10["case"]["status"] == "unclassified",
            body10,
        )
        check("out-of-scope case still gets real contact info, never a dead end", "contact" in body10 and body10["contact"]["email"], body10.get("contact"))
    else:
        print(f"  (skipped: extraction unavailable right now — {r.json().get('detail')})")

    # --- sector coverage is data-driven, not hardcoded ---
    r = c.get("/api/config")
    cfg = r.json()
    check("config lists all 5 sectors", len(cfg["sectors"]) == 5, [s["sector"] for s in cfg["sectors"]])
    check("config reports which LLM provider is live", "llm_provider" in cfg, cfg.get("llm_provider"))

print("\n" + "=" * 60)
print(f"{'ALL CHECKS PASSED' if not FAIL else 'FAILURES: ' + ', '.join(FAIL)}")
print("=" * 60)
sys.exit(1 if FAIL else 0)
