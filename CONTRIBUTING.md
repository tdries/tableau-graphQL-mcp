# Contributing

Thanks for your interest! This is a small, focused MCP server; contributions that keep it
that way are very welcome.

## Development setup

```bash
git clone https://github.com/tdries/tableau-graphQL-mcp && cd tableau-graphQL-mcp
uv sync                       # installs the package + dev tools
uv run pytest                 # tests run offline, no Tableau needed
uv run ruff check .
uv run ruff format .
```

Run the server from source, pointed at your own Tableau site:

```bash
export TABLEAU_SERVER=https://<pod>.online.tableau.com
export TABLEAU_SITE_CONTENT_URL=YourSite
export TABLEAU_PAT_NAME=... TABLEAU_PAT_SECRET=...
uv run tableau-graphql-mcp
# or exercise it interactively:
npx @modelcontextprotocol/inspector uv run tableau-graphql-mcp
```

## Guidelines

- **Keep the tool surface small.** Every tool is tokens in the model's context. Prefer
  extending `graphql_query`/examples over adding a narrow tool.
- **Read-only.** No mutating operations.
- **Stdlib first.** The only runtime dependency is the MCP SDK; keep it that way unless there's
  a strong reason.
- **Secrets via env only**, never as tool arguments, never logged.
- **No writes to stdout**: it carries the JSON-RPC protocol. Log to stderr.
- Add/adjust a test for behavior changes; update `CHANGELOG.md` under `[Unreleased]`.
- A tool rename or required-arg change is a **MAJOR** version bump; call it out in the PR.

## Reporting issues

Open an issue with your Tableau flavor (Server/Cloud + version), whether Data Management is
licensed, and the exact tool call and (sanitized) response.
