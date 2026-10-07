# MCP Browser Bridge privacy notice

The extension connects HTTP/HTTPS website tabs to a companion native application
on your computer. Manual per-tab approval is the default. Approval ends when
revoked, when the tab closes, when Firefox restarts, or when the tab leaves its
approved origin.

You can explicitly enable automatic access to all regular website tabs in the
toolbar popup after acknowledging the warning and granting Firefox's optional
website permissions. This includes existing and future tabs and persists across
restarts while those permissions remain granted. Switching to manual mode stops
broad access and removes the optional host permissions. Private windows, internal
pages and Firefox-protected pages are not supported. No built-in tab-count limit
is imposed; local resources and protocol message-size limits still apply.

Approved tab titles and URLs (without query strings), visible page text and form
values can be transferred to the local application and its connected MCP client.
This can include your name, contact details, location, profile, messages, search
terms, health or financial information, and authentication information visible in
page text. Requested form actions and their results also pass through
the bridge. Approving a tab permits the connected client to read and interact with
that tab; it is not a read-only permission.

The extension has no analytics or external network endpoint. It does not read
cookies or browser storage. Snapshots exclude password inputs, hidden inputs and
controls identified as token, secret or verification-code fields. This filtering
does not guarantee that page text contains no sensitive information.

The extension keeps manual approvals in memory and stores only the selected mode
in extension-local settings. It does not read website/browser storage. Its companion
application relays messages locally. Your chosen MCP/AI client may retain page
content or send it to its service provider: consult that client's privacy settings
and policy before approving sensitive tabs. No claim of end-to-end local-only AI
processing is made.

Source and issue reports: https://github.com/Drima-code/drima-browser-mcp
