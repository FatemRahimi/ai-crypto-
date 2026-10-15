# Security

This document separates controls that exist in Phase 1 from controls that are only planned. A planned control is not protection.

## Implemented in this phase

| Control | Where | What it actually does |
| --- | --- | --- |
| Secret separation | Root `.env`, gitignored. Frontend `.env.local` has only `NEXT_PUBLIC_API_URL`. | Database credentials and `APP_SECRET_KEY` are not in frontend code. |
| Production configuration guard | `Settings` | `APP_ENV=production` rejects debug mode, a wildcard CORS origin, and a placeholder or short `APP_SECRET_KEY`. |
| Reserved secret | `APP_SECRET_KEY` | The value is loaded and checked. It is not used to sign a session, because sessions do not exist. |
| CORS allowlist | `CORSMiddleware` | GET and OPTIONS only. Credentials disabled. Unlisted origins receive no allow-origin header. |
| Security headers | API middleware and Next.js config | `nosniff`, frame denial, referrer policy, permissions policy, and `no-store` on API responses. `X-Powered-By` is disabled on the web app. |
| Request id | API middleware | Accepts a safe client id or generates one. Returned on the response and attached to logs. |
| Validation errors | FastAPI and Pydantic | Malformed input returns a structured 422. Extra proposal fields are rejected. |
| Safe errors | Exception handler | Unhandled exceptions return "Something went wrong." The response does not include the exception text. |
| Structured logs | `app` logger | JSON logs. URLs, bearer tokens, and sensitive mapping keys are redacted. Database probe failures log the exception type, not the message. |
| Execution fail-closed | Risk engine and gateway | Evaluation and submission raise. They do not return an approval. |
| Kill-switch invariant | `ExecutionPolicyDecision` | A decision cannot set `allowed=true` while `kill_switch_engaged=true`. There is no operator button yet. |
| AI import boundary | `app/domains/ai` plus test | The AI package cannot reference the gateway or the authorization function. |
| Browser storage | Frontend test | Application source does not use `localStorage` or `sessionStorage`. |
| Docs hidden in production | FastAPI | `/docs` and `/openapi.json` are off when `APP_ENV=production`. |
| Content Security Policy | Not set | A strict CSP needs a nonce story for Next.js. It is not claimed here. |

`.env.example` uses a local database password. That password is not a production secret. Replace it before the machine is shared.

## Planned, not implemented

These words appear in the product so the shape is visible. They do not protect anything yet.

- MFA
- Passkeys
- Secure sessions and session revocation
- Rate limiting
- Brute-force protection
- Encrypted exchange credentials and rotation
- Audit log writer and audit table
- Operator execution permissions
- Operator kill switch
- Content Security Policy
- Authentication on the API

`GET /api/v1/platform` reports sessions, MFA, passkeys, rate limiting, the audit log, and encrypted exchange credentials as `not_implemented`.

## Credential rules for later phases

- Exchange secrets are collected by the API, encrypted at rest, and never written to the browser, local storage, logs, or git.
- Logs already redact URLs and sensitive keys. Later credential code has to keep using that path rather than printing a client object.
- Withdrawal scope is out of scope permanently. See the constitution.
- The frontend account page does not render a key or secret field in Phase 1.

## Error and input posture

- Pydantic models used for proposals, validation, risk, and policy set `extra=forbid`.
- Production debug cannot be enabled, so the API does not grow a mode that returns exception text.
- Readiness failure is a 503 with a fixed body, not a driver traceback.

## Local trust boundary

Phase 1 assumes a single operator on a local Windows desktop. `python -m app` binds to `API_HOST` and `API_PORT` (default `127.0.0.1:8000`). That is a development posture, not a deployed threat model. If 8000 is occupied, choose another port in `.env` and set the same port in `NEXT_PUBLIC_API_URL`. Do not stop an unrelated process to free the port.

## Phase 1.5 dependency decisions

Audited on 2026-10-15. `npm audit fix --force` was not run.

No non-breaking fix was available. Every advertised npm fix is a semver-major change: Vitest 5.0.4, or an eslint-config-next downgrade to 14.2.35, or Next.js 16.4.1.

| Package | Severity | Where it sits | Decision |
| --- | --- | --- | --- |
| tinypool 1.1.1 | critical | Dev, via Vitest 3.2.7. Not in `npm ls --omit=dev`. | Accept temporarily. The patched line is tinypool 2.x, which Vitest 3 does not use. |
| vitest 3.2.7 and @vitest/mocker | critical / moderate | Direct dev dependency. | Accept temporarily. Fixing it means Vitest 5. |
| braces 3.0.3, micromatch, fast-glob, @next/eslint-plugin-next, eslint-config-next | high | Dev, ESLint only. Latest braces is still 3.0.3. | Accept temporarily. The suggested fix downgrades the Next 15 ESLint config to 14. |
| postcss 8.4.31 | high, plus moderate advisories | Production transitive, nested under next 15.5.28. | Not reachable as a request parser: this app compiles first-party CSS at build time and does not parse visitor-supplied CSS. Leaving Next 15. A move to Next 16.4.1 is a planned upgrade, not a patch. |

Python dependencies are audited with `pip-audit` 2.10.1, a development-only tool. On 2026-10-15 it reported no known vulnerabilities in the installed third-party packages. The local project `ai-crypto-api` is not published on PyPI, so that tool skipped it. Passing pytest is not a vulnerability scan. On this machine Python's default certificate bundle could not verify `pypi.org`; the audit was repeated with the Windows root store in `REQUESTS_CA_BUNDLE` and `SSL_CERT_FILE`. That still verifies certificates. It does not disable TLS.

## Hydration

A Cursor browser session showed a Next.js hydration overlay whose diff was `data-cursor-ref` attributes. Those attributes are injected by that browser, not by this application. On 2026-10-15 the dev server HTML had no `data-cursor-ref`, and headless Chrome loaded the home page with zero such attributes and no hydration console message. Application code does not set `suppressHydrationWarning`.
