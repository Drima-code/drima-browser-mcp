# MCP Browser Bridge privacy notice

The extension connects only manually approved HTTPS tabs on Wellfound and
Chiletrabajos to a companion native application on your computer. Approval ends
when revoked, when the tab closes, or when it leaves its approved origin.

Approved tab titles and URLs (without query strings), visible page text and form
values can be transferred to the local application and its connected MCP client.
This can include your name, contact details, location, profile, application answers
and recruiter messages. Requested form actions and their results also pass through
the bridge. Approving a tab permits the connected client to read and interact with
that tab; it is not a read-only permission.

The extension has no analytics or external network endpoint. It does not read
cookies or browser storage. Snapshots exclude password inputs, hidden inputs and
controls identified as token, secret or verification-code fields. This filtering
does not guarantee that page text contains no sensitive information.

The extension keeps approvals in memory, not persistent storage. Its companion
application relays messages locally. Your chosen MCP/AI client may retain page
content or send it to its service provider: consult that client's privacy settings
and policy before approving sensitive tabs. No claim of end-to-end local-only AI
processing is made.

Source and issue reports: https://github.com/Drima-code/drima-browser-mcp
