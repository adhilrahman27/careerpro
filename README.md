# CareerRadar Pro — Working Self-Hosted Starter (v0.4.0)

**Status: functional local MVP, NOT production-ready or commercially sellable yet.**

CareerRadar Pro is an original job discovery application inspired by the attached product specification. It contains a persistent Python/FastAPI backend, SQLite database, responsive installable PWA, React Native/Expo Android+iOS client source, data-provider adapters, security controls, tests, and deployment guidance.

**No live job board, subscriptions, AI provider, push notifications, or production Supabase project is configured.** Real vacancies appear only after adding authorized feeds or verified manual listings. No fake jobs are displayed in normal operation.

## Ready-to-build Android test APK

The package now includes an offline UI demo for Android and an automated GitHub Actions APK build workflow. See **ANDROID-TEST-APK.md**. This bundle is not a precompiled APK, and no APK was successfully built in the authoring environment.

## Quick start — Windows 10/11

Install Python 3.13 or another supported Python version, then open PowerShell in the extracted project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Go to **http://127.0.0.1:8000/** on the **same computer**.

For Mac/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Registration is open and creates a **seeker** account. To become the **first admin**, register normally, STOP the web server if desired, and run this separate console command:

```bash
python -m server.bootstrap_admin your-real-email@example.com
```

The admin role is never granted by client-side signup fields. Sign in with the same registered account and open **Admin console** in the sidebar. Add a Greenhouse or Lever company board slug (after checking data rights), or create a direct vacancy with a legitimate HTTPS employer application URL. Click **Sync now**. Do not use unauthorized third-party content.

### Start server-side alert evaluations

In a second terminal with your Python environment activated:

```bash
python -m server.worker
```

The worker syncs configured sources, then evaluates alerts and writes repeat-free in-app notifications. It does not deliver native push/email. In development this runs independently of the UI. For commercial use, deploy it with a supervised job runner, observability, backoff and source licence checks. The stored alert frequency settings are not yet enforced as digest intervals.

### Android PWA installation

Host the site on an HTTPS domain, open it in Chrome on Android, and select **Add to Home screen / Install**. This is an **installable website**; it is **not an APK** and cannot be published directly as a Play Store native package.

### Android/iOS native project

A React Native/Expo Router client is supplied in `apps/mobile`. It uses the same REST API for browsing, sessions, saved jobs, alerts, tracker and profiles. On a connected development machine:

```bash
cd apps/mobile
npm install
npx expo install --fix
# Set EXPO_PUBLIC_API_BASE_URL=https://your-real-domain.example in apps/mobile/.env
npx expo start
```

The Android emulator can use `http://10.0.2.2:8000` **only for local development**. Production requires HTTPS, a proper native application ID, signed builds, and an Expo/Google Play account. As dependencies could not be downloaded here, the native client has **not** been built or device-tested.

Preview Android APK (once build credentials and an Expo account are configured):

```bash
npx eas build -p android --profile preview
```

Production Android AAB:

```bash
npx eas build -p android --profile production
```

Do not claim these commands have been successfully run in this environment.

## Features actually implemented

- Account registration, password login, revocable bearer sessions, sign-out, account deletion and personal JSON export
- Private professional profile with skills, job preferences and summary
- Real-database job search, location filter, pagination, sorting and employer source links
- Greenhouse / Lever feed adapters; operator-configured; mocked with provider-independent unit integration tests pending
- Manual administrator job posting (not employer self-service)
- Saved jobs and keyword/location alert rules
- Server-side in-app alert evaluation with repeat suppression (worker process)
- Job application tracking with status updates and CSV export
- CV upload (TXT/PDF/DOCX), per-user file isolation, download/delete and a basic PDF generated from profile fields
- Explainable rule-based job relevance score (not AI)
- Protected admin overview, source setup and ingestion log
- Job reporting to administrator database
- Installable responsive PWA with offline shell cache only
- Native Expo source wired to real backend for core screens
- Basic API integration tests and visual smoke render

## Functionality NOT implemented or not fully verified

- Supabase production backend/Auth/RLS integration. `supabase/schema.sql` is a schema **reference**, not a deployed migration; actual app runs SQLite.
- Ingestor jobs have not been fetched live in this environment because outbound registry/network access is unavailable; commercial redistribution permissions must be checked per source.
- Google/Apple SSO, email verification, password recovery, MFA or password reset
- General AI assistant, complex ATS analysis, speech interview and semantic search. v0.4 adds private CV/cover-letter tailoring and optional consent-gated AI rewriting (requires a configured provider; not live-verified).
- Native Firebase/Expo push notifications, email alerts, verified scheduled 2-hour/daily digest behavior
- Stripe/Google Play Billing/Apple IAP and live subscription entitlement verification
- Employer self-service, moderator console, multi-tenant white labelling
- Full security audit, commercial privacy/legal review, production backup restoration tests
- Real Android APK/AAB builds and physical-device/native UI tests
- Store approval, domain deployment, uptime checks, independent penetration tests

Never upload the starter directly to Google Play or market it as fully tested. See `docs/RELEASE-STATUS.md`.

## Testing

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest -q tests    # Windows PowerShell: $env:PYTHONPATH='.'; pytest -q tests
PYTHONPATH=. python tests/browser_smoke.py  # Optional: requires Playwright + Chromium
node --check web/assets/app.js
python -m compileall -q server
```

The API tests use temporary databases and do not touch user data.

## Project map

| Folder | Purpose |
|---|---|
| `server/` | FastAPI, persistence, auth, ingestion worker |
| `web/` | Responsive PWA, CSS/JS and original icons |
| `apps/mobile/` | Expo Router native Android/iOS source |
| `supabase/` | Security-conscious PostgreSQL reference schema |
| `tests/` | FastAPI integration tests |
| `docs/` | Specification, release gates, preview images, operations |

## Architecture notes

Browser/PWA and Expo call `/api/*` endpoints with bearer sessions. The server owns user resources and provider ingestion. SQLite is stored at `var/careerradar.sqlite3` by default. The in-process rate limit is for local use; replace with distributed rate limiting. `server.worker` polls permitted sources and evaluates alert rules. Profiles and CV files never travel to third-party AI services in this starter.

Do not put this server behind a public domain without TLS, additional rate limits, email verification, production-safe monitoring and backup procedures. This is a product foundation, not finished commercial software.

## Update: CareerRadar v0.3 — 12 career intelligence additions

See [docs/FEATURES-V0.3.md](docs/FEATURES-V0.3.md) for the honest feature-by-feature matrix, implementation differences between the web and Expo client, exact tests, and required external integrations. The new Career tools, Walk-in interviews, Job comparison and My insights sections are present in the web application. A new Tools tab and enhanced vacancy actions were added to the React Native Android/iOS source. **This ZIP does not contain a compiled APK.** The existing GitHub Actions workflow can attempt a test APK build but has not been verified on a native runner. No connected production Supabase project was modified.

## v0.4: Job-specific CV and cover-letter documents

The vacancy detail page now has **Tailor CV + Letter**. Users can choose an uploaded original CV, select professional/concise/formal wording, generate private documents, review and edit their drafts, and download PDF or DOCX versions from the web. Each vacancy has its own saved versions in **Tailored documents**. The system only uses user-supplied CV/profile facts; the default rule-based matching does not contact an external AI provider.

Optional AI rewrite uses the OpenAI Responses API, **only** if an operator supplies `OPENAI_API_KEY` on the server and the user explicitly checks consent. Configure `OPENAI_MODEL` if desired (default `gpt-5.4-mini`). Do not put an API key in an Expo or frontend variable. AI is disabled in this supplied package, and live AI provider behavior has not been tested. External AI processing may incur costs and third-party retention obligations.

See [docs/FEATURES-V0.4.md](docs/FEATURES-V0.4.md) and [docs/QA-V0.4.txt](docs/QA-V0.4.txt) for endpoints, privacy controls, exact tests and limitations. This is **not** a release-ready APK or commercial product.
