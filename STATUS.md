# Status — 2026-10-05

## Optional regular-Firefox connector

Added experimental activeTab + nativeMessaging connector for explicitly approved
Wellfound/Chiletrabajos tabs. Toolbar approval/revocation; leaving origin revokes.
Separate regular-stdio MCP and regular-call diagnostics; original MCP unchanged.
Private Unix socket; no cookies, OAuth pages, arbitrary evaluation or all-site
permissions. Top-frame snapshots and one strict action per call; manual uploads.
Six synthetic connector tests pass, including real native-host IPC roundtrip,
origin revocation, duplicate-match rejection and sensitive-control exclusion.
Full suite: 25 tests passed in 27.07 seconds; Ruff/lockfile/diff checks passed.
Original authenticated transport smoke test still passes.
Native host registered locally and separate MCP configured. Live regular-browser
use awaits user loading temporary extension and toolbar approval; not yet verified.

## Public distribution preparation

David authorized public GitHub distribution under MIT. Added license, package
metadata, clone instructions and Google sign-in troubleshooting. Reviewed tracked
files and all four existing commits for credential/personal-data patterns; no
credentials, browser profiles or personal screenshots found. Runtime state stays
outside git. Historical synthetic tests and transport checks rerun before release.
Release checks: 19 tests passed in 25.37 seconds; Ruff and lockfile checks passed;
authenticated HTTP/stdio transport, image forwarding and reconnect smoke test passed.
Google rejected the dedicated Firefox OAuth flow too; use supported site login
or a regular non-automated browser, never a security bypass.

The older notes below describe initial September verification, not current job
application state. Actual application receipts remain in the private job-search
repository and are not part of this public project's release materials.

Implemented 14 browser MCP tools using official MCP SDK and Playwright.
Default engine Firefox; optional Chromium, isolated persistent profiles.
Local authenticated HTTP service plus stdio proxy for Codex/Kimi; no extension.

## Verified

- 19 tests passed in 36.65s: Firefox/Chromium synthetic forms, uploads, downloads,
  strict locators, iframe fields, dialogs, cookies across restart, batch stopping,
  MCP image output and local authentication/Origin rejection.
- Transport smoke test passed using Firefox: authenticated HTTP, stdio discovery,
  screenshot forwarding, browser survives two client reconnects.
- Ruff checks passed. Matching Firefox 1538 and Chromium 1234 installed.
- User service installed and active; Codex and Kimi configuration registered.
  Blueprint disabled in Codex. Native tools appear after client reload; diagnostic
  CLI already uses real MCP to work in the current session.
- Dedicated visible Firefox opened GetOnBoard and returned a verified screenshot.
- Initial Chromium Google OAuth was rejected; Firefox email sign-in subsequently succeeded.
  No stealth or account-security changes. Existing regular Firefox profile untouched.
- Job-search handoff updated with current schema and bounded Kimi tasks.
- Dedicated headed Firefox windows are hidden from focus and normal Alt-Tab space
  shortly after launch using the local window manager when `DISPLAY` and `wmctrl`
  are available. The browser remains authenticated and can be brought forward for
  manual CAPTCHA or sign-in work.

## Remaining

Human email sign-in verified. Live GetOnBoard CV upload, Trix form filling and
Chosen dropdown selection verified. No real job application submitted or receipt
observed: STEUART requires a portfolio website, rejecting a GitHub profile URL.
Pointer actions later stalled at Firefox stability checks; verified enabled buttons
worked using normal keyboard Enter. Custom Chosen dropdown required its visible
search input rather than the hidden select. These observations are recorded in
the job-search skill; no force-click, hidden mutation or validation bypass used.
Kimi model-driven browser discovery is not yet tested and model alias is not
confirmed as 2.8. Application-specific skill remains pending live success.

Repository is prepared for public distribution. Browser data lives outside git under
`~/.local/share/drima-browser`. Do not publish tokens, profiles or personal evidence.
