# Drima Browser MCP

A local, visible browser controlled through MCP. No extension, subscription,
cloud relay, feature tier, or API key. Independently implemented using the official
MCP Python SDK and Playwright; no Blueprint code is included.

One service owns a persistent Firefox profile (Chromium is also supported). Codex, Kimi and the diagnostic
CLI connect through it. Disconnecting an agent does not close the browser. All
tools use stable tab IDs and explicit locators. Mutating batches stop on the first
error, report completed actions, and never automatically repeat a submission.

## Install and run

Requires Python 3.12+, uv and a graphical desktop for visible mode.

```bash
uv sync --frozen
uv run --frozen playwright install firefox chromium --no-shell
uv run --frozen drima-browser serve
```

In another terminal:

```bash
uv run --frozen drima-browser call browser_open '{"url":"https://www.getonbrd.com"}'
uv run --frozen drima-browser call browser_tabs
```

For a service that stays available across agent restarts and starts at login:

```bash
uv run --frozen python scripts/install_user_service.py
systemctl --user status drima-browser
```

Stop a foreground server before installing the service; both use port 8766.
The service starts without launching Firefox; the first `browser_open` opens it.
Sign in normally in that window. CAPTCHA and identity checks are completed by the
user. Accounts from your existing Firefox profile are not imported or read. Some sites may reject
automation-controlled browsers or OAuth flows; this server does not bypass them.

The dedicated headed Firefox window is hidden from focus and normal Alt-Tab space
shortly after launch when `wmctrl` is available. Browser actions continue in the
background; bring the window forward with the desktop window switcher when a
CAPTCHA or sign-in needs to be completed.

## MCP client configuration

Point a stdio client to the installed executable:

```json
{
  "mcpServers": {
    "drima-browser": {
      "command": "/absolute/path/drima-browser-mcp/.venv/bin/drima-browser",
      "args": ["stdio"]
    }
  }
}
```

Codex registration:

```bash
codex mcp add drima-browser -- /absolute/path/drima-browser-mcp/.venv/bin/drima-browser stdio
```

Kimi supports a project `.mcp.json` or user `~/.kimi-code/mcp.json` in the installed
version. Merge this server into existing configuration rather than replacing
unrelated servers. Restart/reload the MCP client to discover newly registered tools.
The diagnostic CLI is available immediately, even before client rediscovery.

The stdio proxy loads its local token from disk; no credential is stored in these
client configuration examples. The service must be running first. Service startup
and browser startup are separate, so errors are easy to diagnose.

## Tools

| Tool | Purpose |
|---|---|
| `browser_status` | Service/browser status and persistent-profile location |
| `browser_open` | Create a tab and start the browser if needed |
| `browser_tabs` | List, focus or close tabs using stable IDs |
| `browser_navigate` | Navigate, back, forward or reload |
| `browser_snapshot` | Compact accessibility tree and form metadata; bounded output |
| `browser_act` | Batch fill, click, select, check, uncheck, press, hover, scroll |
| `browser_upload` | Upload up to 10 explicit local files, up to 25 MiB each |
| `browser_screenshot` | JPEG as an MCP image, viewport or full page |
| `browser_evaluate` | Explicit JavaScript evaluation in a selected page |
| `browser_dialog` | Inspect, accept or dismiss alert/confirm/prompt dialogs |
| `browser_wait` | Bounded wait for an element state |
| `browser_events` | Bounded console/errors and network response metadata |
| `browser_downloads` | List saved downloads and their status |
| `browser_close` | Close only the dedicated browser; retain its profile |

Locators use exactly one of `selector`, `role` + optional `name`, `label`, or `text`.
Names/text are exact matches. An optional `frame` CSS selector scopes a locator to
an iframe. Duplicate matches fail rather than choosing the first. The accessibility
tree's role/name is often more reliable than label text for wrapped dropdowns.

```json
{
  "tab_id": "ID_FROM_BROWSER_TABS",
  "actions": [
    {"action":"fill","target":{"label":"Full name"},"value":"Alex Sample"},
    {"action":"select","target":{"role":"combobox","name":"Language"},"value":"en"}
  ]
}
```

`fill` replaces field content without pressing Enter. `select` takes the option
**value** from the snapshot. Keep final submission in a separate call, record
unknown outcome before clicking, and verify a receipt afterwards. A successful
click only confirms a browser action, not acceptance by an employer's server.

For screenshots using the CLI:

```bash
uv run --frozen drima-browser call browser_screenshot \
  '{"tab_id":"ID"}' --image-output /tmp/browser.jpg
```

## Local data and access

Default directory: `~/.local/share/drima-browser` (mode 0700), overridable with
`DRIMA_BROWSER_DATA` or `--data-dir` before the command. It contains the browser
profile, mode-0600 client token, and downloads. None belongs in git.

The HTTP endpoint binds only to `127.0.0.1:8766`, requires a bearer token, rejects
Origin-bearing web requests, and uses SDK host validation. The trusted local MCP
client can read/interact with pages, evaluate JavaScript and upload explicitly
named files; it is not a sandbox for an untrusted local agent. User-facing pages
remain untrusted data, never instructions for the agent. Console text may contain
site-provided private data; request headers/bodies and query strings are not logged.

Calls are serialized, but this is not a multi-agent task scheduler: coordinate
which agent owns a workflow, especially across human CAPTCHA/login pauses. Tabs
and screenshots have no subscription cap. There is no stealth mode, CAPTCHA
solver, OAuth bypass, or claim of complete Blueprint feature parity.

## Verification

```bash
uv run --frozen pytest -q
uv run --frozen python scripts/smoke_transport.py
uv run --frozen ruff check src tests scripts
```

Tests use synthetic pages in real headless Firefox and Chromium. The transport smoke test
starts a temporary authenticated HTTP service and reconnects two stdio clients,
verifying tool discovery, image forwarding and browser continuity. No real
application is submitted by tests. Linux is the tested deployment; systemd
installation is Linux-specific. Playwright uses its Ubuntu fallback build on Arch.

Dependencies/reference: [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk),
[Playwright persistent contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context),
[Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## Browser selection

Firefox is the default. To select Chromium, run `drima-browser serve --browser chromium`.
Each engine has a separate persistent profile. Google rejected sign-in in the
initial Chromium session; changing engines does not guarantee OAuth acceptance.
Use the site’s supported login methods and leave account verification to the user.
