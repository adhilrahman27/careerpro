# CareerRadar Pro v0.4 — Tailored CV & Cover Letter Builder

**Status:** Local backend and web workflow implemented and tested. Native React Native source updated, but NOT compiled into an Android APK or tested on a physical device. NOT a commercial production release.

## New workflow

1. Sign in and complete your professional profile under **My profile**.
2. Open **My resume** and upload an existing text-based PDF, DOCX or TXT CV. Scanned images without selectable text may not yield useful source text.
3. Open an active vacancy with a real description and choose **Tailor CV + Letter**.
4. Select the source CV (or profile-only), document type and writing style.
5. Choose **Private matching** (no external AI), or, if the server has an `OPENAI_API_KEY`, opt in to AI-enhanced rewriting with the explicit external-processing consent checkbox.
6. Generate separate CV and cover-letter drafts. These are owned only by the account that created them.
7. Open **Tailored documents** to edit, save, delete or download each version as **PDF** or **Word DOCX**.
8. Review every detail and verify all qualifications before manually applying on the original employer website.

## Backend routes

| Route | Purpose |
|---|---|
| `POST /api/jobs/{job_id}/tailor` | Generate one or both drafts from the job and selected candidate CV/profile |
| `GET /api/tailored` | List this user's drafts |
| `GET /api/tailored/{id}` | Read an owned draft |
| `PUT /api/tailored/{id}` | Save edited content and title |
| `DELETE /api/tailored/{id}` | Delete an owned draft |
| `GET /api/tailored/{id}/export.pdf` | Authenticated PDF download |
| `GET /api/tailored/{id}/export.docx` | Authenticated Word download |

Required JSON for generation: `{"kind":"both", "cv_id":"<your CV ID or null>", "tone":"professional", "mode":"local", "allow_external_processing":false}`.

## Privacy and accuracy behavior

- Default mode uses rule-based skill matching and existing profile/CV content. It does **not** send data to an external AI provider.
- Optional AI calls OpenAI Responses API with `store: false` and only after explicit consent. Third-party retention and privacy terms may still apply; read and disclose them prior to commercial launch.
- API keys must remain server-side. `OPENAI_MODEL` defaults to `gpt-5.4-mini`, configurable by the operator.
- When no AI key is configured, the optional AI mode is hidden in the UI and server calls return a clear error.
- Unsupported recognized skill claims trigger an AI-output rejection, but this is **not** a comprehensive hallucination validator. Human review is mandatory.
- Each document is stored with a user owner and access is checked for every read, update, delete and export.
- Existing SQLite FK cascade removes generated drafts upon user deletion. A related CV deletion keeps existing drafted text but clears the CV reference. Drafts contain candidate data and must be deleted separately or via account deletion.
- An application is **not** sent when documents are created or downloaded.

## Implementation differences

**Web/PWA:** Full generation wizard, document library, editable text, server-side PDF and DOCX downloads.

**Expo Android/iOS source:** Job detail button, generation options, consent, document library, editable drafts, native text sharing. Native PDF/DOCX download interface has not been built (use web export). No native Android binary has been compiled.

**Offline mobile demo:** Intentionally blocks generation from fictional sample vacancies and explains that a configured API server is required.

## Verification (28 Oct 2026)

- 13 API tests passed, including two new feature test cases.
- Browser TestClient-bridge smoke passed: vacancy → select CV → generate both documents → edit → save → list.
- Existing browser smoke passed.
- JavaScript syntax checks passed.
- TypeScript/TSX syntax transpilation passed for the modified mobile files; this does not validate native module dependencies or produce an APK.
- PDF and DOCX files were produced, rendered to page images and inspected locally; no visible clipping on the representative one-page sample.

## Remaining blockers

1. A real, authorized commercial job source and employer data-rights validation.
2. Secure commercial deployment, production Supabase/PostgreSQL migration, backups and operational monitoring.
3. Native Android build and physical-device test.
4. Real OpenAI API credential, provider billing, privacy notices, usage limits and mock/live evaluation for AI mode.
5. Advanced ATS templates and structured CV parsing of multi-column or scanned PDFs.
6. External security audit and legal/Play Store compliance review.
