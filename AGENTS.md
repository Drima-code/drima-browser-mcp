# Drima Browser MCP

Local browser MCP, no subscription or external relay. Read README.md and STATUS.md.
Use `uv run --frozen` and the committed lockfile. Test with synthetic local pages;
never use live job submissions as regression tests. Browser profiles, tokens and
screenshots belong outside git. Preserve strict element matching and never retry
mutating browser actions automatically. Timeout means outcome may be unknown.
Keep the service on loopback with bearer authentication and reject browser Origins.
Use the official MCP SDK; do not copy Blueprint code. Maintain a concise status
record and commit tested milestones. No AI attribution in commits.
