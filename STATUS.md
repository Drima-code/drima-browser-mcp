# Status — 2026-09-27

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

Repository is private. Browser data lives outside git under
`~/.local/share/drima-browser`. Do not publish tokens, profiles or personal evidence.
