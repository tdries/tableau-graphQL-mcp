# Security

## Reporting a vulnerability

Please report security issues privately to **tim.dries@biztory.be** rather than opening a
public issue. You'll get an acknowledgement within a few business days.

## Security model

- **Read-only.** The server only issues GraphQL queries against the Tableau Metadata API.
  There are no mutating tools, no SQL execution, and no shell access.
- **Local, stdio only.** It runs as a child process of your MCP client and communicates over
  stdin/stdout. It opens **no inbound network port**.
- **Credentials from the environment only.** The PAT/token/cookie are read from environment
  variables at startup. They are never exposed as tool arguments, never written to logs
  (logging goes to stderr, not the protocol stream), and never returned in tool output.
- **Least privilege.** Requests use your Personal Access Token, so results are scoped to what
  that Tableau identity is permitted to see. Create a dedicated, minimally-scoped PAT.
- **Outbound only to your Tableau host** (`TABLEAU_SERVER`) over HTTPS.

## Recommendations

- Use a dedicated PAT with the least privilege required; rotate it periodically (PATs expire
  after 15 days of non-use, or 1 year).
- Pin a released version in production (`...@v0.1.0`) and review the tool catalog before
  granting an agent access.
