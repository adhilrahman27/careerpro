# CareerRadar Pro — v0.3 requested feature integration

**Updated 28 October 2026**. This is a functional development build, **not a commercial-release-ready app**. There is no compiled APK in this package. Android source and the GitHub cloud build workflow remain unverified on a device.

| Requested addition | Status in v0.3 | What actually works / remains |
|---|---|---|
| 1. Job authenticity radar | **Partial, functional** | Job detail screens show source provenance, first/last observed timestamps and freshness. Neither employer identity nor application link is independently verified; those flags explicitly remain false. No live dead-link scanning yet. |
| 2. Automatic email application tracking | **Manual workflow implemented** | Paste email text in web Career Tools. Server suggests conservative keyword classification; user chooses an existing application and explicitly confirms any status change. No Gmail/Outlook OAuth, background inbox monitoring or automatic status updates. Native client can preview status but does not yet confirm it. |
| 3. UAE walk-in interview radar | **Functional with manual curation** | Admin can create/publish interview events (start/end time, venue, URL, requirements, documents); users view future published listings. No automatic event discovery or external employer verification. No fictional events shown as real. |
| 4. Smart application assistant | **Partial, functional** | Rule-based, user-specific cover-letter draft and CV-writing notes based on a selected real job and saved profile; never submits an application. No LLM tailoring or approved third-party one-click apply. |
| 5. WhatsApp alerts | **Manual job sharing only** | WhatsApp share-link preview for authenticated job seekers, with user choosing recipient and pressing Send. Automated messaging requires WhatsApp Business approval, templates and explicit user opt-in. |
| 6. Job comparison | **Functional** | Select 2–4 vacancies in web and Android; compare known company, title, location, source freshness, published salary and work arrangement. No invented benefit/salary figures. |
| 7. Commute-based job search | **Directions link only** | Construct official Google Maps directions URLs from user-provided origin and published job location. No commute duration estimation, route optimization, transit service SLA, or commute-time filtering. |
| 8. UAE offer letter verification | **Safety checker only** | Rule-based detection of some fee/access-code warning terms; links to MOHRE. Not connected to MOHRE verification records. Never claims an offer is authentic. |
| 9. AI career growth roadmap | **Rule-based plan** | Extracts small set of explicitly mentioned software/skills, compares declared profile and offers generic learning recommendations. No external courses, accreditation verification or LLM coaching. |
| 10. Recruitment activity signals | **Source observability only** | First-seen and last-source-ingestion dates available; actual employer response rates, candidates applied, active hiring verification are `null` / false. |
| 11. Secure CV sharing | **Functional on web/server** | Private expiring, revocable 256-bit-equivalent opaque links with max-open limits, SHA-256 token hashes, per-user access controls and cache/noindex headers. Link opens are **not proof a human read the CV**; anyone possessing the link can access before expiry. Mobile view/revoke supported with connected API, creation via web. |
| 12. Weekly performance report | **Functional** | 1–26 week overview based on database application, saved and in-app notification records, plus due follow-up list. Background worker creates a single in-app follow-up reminder per due-date/application; no external calendar, email or push notifications. |

## Platform coverage

- **Web**: Fully navigable Career Tools, comparisons, walk-in events, offer warnings, email review/confirmation, CV sharing, weekly insights, application kit, skill roadmap, WhatsApp share and Maps links.
- **Android/iOS source**: New Career Tools tab; job details expose authenticity metadata, comparisons, rule-based cover letters/skill roadmap, manual WhatsApp sharing and Maps directions. Offline demo mode stays clearly labelled and does not claim live integration. CV upload/share creation requires the web interface; some extended features are backend/web only.
- **Backend**: All 12 domains have endpoints or safe, clearly disabled integration status. External credentials and production data agreements have **not** been configured.

## Testing performed

- `PYTHONPATH=. pytest -q` — 10 passed (6 original + 4 new integration/security tests).
- `PYTHONPATH=. python tests/browser_smoke.py` — browser registration, account, alert, application, pasted-email review and confirmation, report, walk-in and career tools navigation passed with a FastAPI TestClient bridge. This is *not* a publicly deployed end-to-end test.
- `node --check web/assets/app.js` — passed.
- `python -m compileall -q server` — passed.
- TypeScript transpilation of 14 mobile TS/TSX files — no syntax diagnostics. **Native dependency typecheck, Gradle build and physical-device tests not performed.**

## Business / production blockers

1. Migrate SQLite prototype to a dedicated production Postgres/Supabase project with fully tested authorization/RLS, backups and data deletion policies (the connected LittleBloom project was NOT modified).
2. Obtain permissions and commercial licences for each real job source; review ingestion reliability and actual jobs before display to customers.
3. Configure Gmail/Outlook OAuth per-user and consent, WhatsApp Business messaging, a routing API and appropriate per-provider quotas before promising automation or route filters.
4. Perform legal, privacy, fraud/risk model and security reviews. Implement proper public CV link abuse prevention, expiring sessions, email verification and admin MFA.
5. Build native APK/AAB with actual Expo dependencies and Android SDK on an external runner; test on real devices. Store billing, subscriptions and other master-prompt features remain unimplemented.
6. Do not describe this package as bug-free, store-approved, commercially verified or fully complete.

## Local use

```bash
pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=. uvicorn server.main:app --host 127.0.0.1 --port 8000
# visit http://127.0.0.1:8000
# second terminal for alerts and follow-up reminders:
PYTHONPATH=. python -m server.worker
```

All production secrets must stay out of version control. Do not open this self-hosted starter to the public internet without hardening and independent review.
