# Operations and external configuration

## Runtime topology

- Web server: `uvicorn server.main:app` (API + static PWA), behind HTTPS reverse proxy.
- Background worker: `python -m server.worker` in a separate supervised process.
- Local durable state: SQLite + local CV file directory under `var/`.
- Job sources: Greenhouse or Lever public posting interfaces selected by admin. Confirm commercial permission, attribution, terms and rate limits for each board before redistribution.
- Web app: HTML/CSS/JS inside `web`; no external JS dependency.
- Native source: Expo React Native Router under `apps/mobile`.

## Suggested deployment path

1. Register a distinct company domain and configure HTTPS.
2. Use private network ingress/security groups and an application server with continuous monitoring.
3. Transition DB to a dedicated managed PostgreSQL service before using replicas/scale-out. The Supabase schema is only an architecture reference and requires API updates.
4. Store CV files in private object storage with per-user authorization, antivirus handling, encryption and retention controls.
5. Set managed process worker, restart policies, centralized log collection and distributed throttling.
6. Lock source versions and configure CI checks.
7. Implement commercial audit and release blockers in RELEASE-STATUS.md.

## Data protection notes

User sessions are revocable and expire automatically. The current SPA session token is in browser sessionStorage (not persistent across full browser restarts), so XSS protection remains important. For a production web implementation, migrate to properly configured HttpOnly cookies, CSRF controls and additional session defenses. Native use Expo SecureStore.

If exposing the account deletion feature, also publish a public deletion request URL compliant with current Play Store policy. Deleting active database records does not automatically erase retained backups; configure retention.

## Backups

At minimum, back up the SQLite database consistently and the `var/uploads` tree. Do not copy SQLite database while writes are in flight without SQLite backup API. Protect backups, document retention and restore to a clean test environment. This runbook does **not** claim a successful restore test.

## Support / privacy / terms

Real legal notices, privacy statement, processing basis, consent records, data retention, incident response and support channels need owner-specific input and legal review. `GET /api/legal/privacy` and `/terms` explicitly return draft notices, not misleading finished policies.

## API docs

After starting the backend, open `/api/docs`. The OpenAPI document is `/api/openapi.json`.

## Production support cost

No benchmarked production hosting cost is established; provider charges depend on usage, data licences, CV storage, AI API tokens, payment volumes and notifications. Use real observed traffic and quotations to model cost.
