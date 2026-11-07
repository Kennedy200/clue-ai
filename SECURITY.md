# Security

Please report vulnerabilities privately by opening a GitHub security advisory on this repository rather than a public issue.

## Security checklist (completed 2026-11-06, verified by automated tests unless stated)

**Accounts and sessions**
- [x] Passwords hashed with argon2id; never logged or returned.
- [x] Session cookie `HttpOnly`, `SameSite=Lax`, `Secure` when `SITE_URL` is https; random 256-bit token stored only as a SHA-256 hash.
- [x] CSRF token required on every state-changing request (`x-csrf-token`); tested on billing and password routes.
- [x] Login lockout and per-client rate limits on signup, login, reset, contact, billing, score. The client address is read from `X-Forwarded-For` behind our own proxy (a test proves one visitor cannot lock out another).
- [x] Password reset and email-verify tokens are single use and expire; reset and password change sign out other devices.
- [x] No account enumeration on "forgot password".
- [x] A stranger cannot become admin by signing up with `ADMIN_EMAIL` on a hosted install: the address must be verified first (found and fixed in this review).
- [x] Suspended and deleted users lose access on their next request.

**Data access**
- [x] Every project, job, asset, transcript, clip, calendar post and invoice is checked against its owner; other users get 404 (tested across the main endpoints).
- [x] Team membership is checked on every team route; non-members get 404 so team ids are not revealed.
- [x] Files are served only through short-lived HMAC-signed links; path traversal is refused; users can only sign their own folder.
- [x] Uploads: allow-listed types, probed with FFprobe, size limits per plan, resumable chunks validated by offset.
- [x] Credits cannot go negative; reserve, settle and refund are idempotent; the ledger is append-only and balance = sum of the ledger (tested, including after a restore).
- [x] Referral rewards are paid only after the friend verifies their email, once per friend, at most 50 per referrer (found and fixed in this review).

**Secrets**
- [x] OpenRouter key and YouTube client secret and tokens are stored encrypted (Fernet); the key file `storage/.secret` is outside git.
- [x] Secret scan before every push (`npm run scan`; also in CI). No keys in the repository.
- [x] Backups contain that secret: documented in the runbook.

**Web**
- [x] Content-Security-Policy (default-src self, no framing, no objects), `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, HSTS on https. The public pages load with zero console errors under this policy (e2e).
- [x] Oversized request bodies are refused (4 MB, 64 MB for upload chunks).
- [x] Admin spreadsheet export neutralises cells that start with `=`, `+`, `-` or `@` (formula injection); import is validated first and applied all-or-nothing.
- [x] Outbound image imports use an allow-list of hosts; arbitrary URL import is off by default (`FEATURE_URL_IMPORT=false`).
- [x] Prompts treat user text as data (`<data>` wrapping), AI output is schema-validated.

**Dependencies** (audited 2026-11-06)
- [x] Python: `pip-audit` reports no known vulnerabilities after upgrading FastAPI/Starlette, cryptography, python-multipart and pytest; versions are pinned in `apps/api/requirements.txt`.
- [ ] npm: `npm audit --omit=dev` still reports PostCSS inside Next.js 15 (moderate/high, build-time CSS stringify and source-map handling). Clue AI does not run PostCSS on user-supplied CSS, so it is not reachable by users; the fix needs Next 16. Re-check each release.

**Known gaps (be honest with yourself before going live)**
- Billing is simulated, so there is no payment-data handling yet. When you add a gateway, never store card numbers; redirect to the gateway's hosted page.
- The login lockout and rate limiter are in memory (one API process). If you run several API processes, move them to Redis.
- No two-factor authentication yet.
- No automated malware scan on uploaded files (they are only decoded by FFmpeg, never executed).
- The Docker/Caddy deployment files have not been run end to end.
- No external penetration test has been done.
