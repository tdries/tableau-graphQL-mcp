# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/). Note that the **tool schema is the public
API**: renaming a tool or a required argument is a MAJOR change.

## [Unreleased]

## [0.1.3] - 2026-10-14

### Security
- Require `mcp>=1.28.1` (was `>=1.2.0`), the first SDK release with no known advisories:
  GHSA-9h52-p55h-vw2f (CVE-2025-66416), GHSA-hvrp-rf83-w775, GHSA-jpw9-pfvf-9f58,
  GHSA-vj7q-gjh5-988w and older ones. These affect the SDK's HTTP/WebSocket transports, not
  this stdio server, but the old floor still allowed installing a vulnerable SDK.
- Refresh `uv.lock`, which clears all open Dependabot alerts in the dev environment:
  PyJWT 2.13.0 -> 2.15.1, anyio 4.14.1 -> 4.15.1, cryptography 49.0.0 -> 50.0.2.
- Harden the read-only guard: a mutation separated from a preceding operation by a comma,
  a BOM, a block string (`"""..."""`) or nothing at all (`query{a}mutation{b}`) slipped past
  the old regex. `_is_write` now ignores everything inside selection sets and rejects the
  `mutation`/`subscription` keyword anywhere at the document's top level (fails closed).

### Fixed
- Pin the MCP SDK below 2: mcp 2.0.0 removed `mcp.server.fastmcp`, so any fresh install
  (e.g. `uvx tableau-graphql-mcp`) resolved 2.0.0 and crashed on import with
  `ModuleNotFoundError`. Locked environments (`uv.lock`) were unaffected. Migration to the
  2.x SDK API is tracked separately.
- PAT sessions are re-signed-in proactively when Tableau's reported
  `estimatedTimeToExpiration` runs out (60 s margin), instead of only after a 401/403.
- A non-JSON Metadata API response (e.g. an HTML login or proxy page) now raises a clean
  `TableauError` instead of a raw `JSONDecodeError`.
- Best-effort calls (`/api/serverinfo`, HTTP error-body reads) catch only network and parse
  errors instead of bare `Exception`, so real bugs surface.

### Added
- `TABLEAU_LOG_LEVEL` (default `INFO`). `DEBUG` logs every HTTP call as method + URL to
  stderr; headers, bodies and secrets are never logged.

## [0.1.2] - 2026-07-13

### Changed
- Docs only: the README roadmap now reflects that PyPI and the MCP registry are shipped,
  and two badges that rendered broken on the project page (pepy downloads 404, an
  unconnected Codecov "unknown") were removed. Republished so the PyPI page matches.

## [0.1.1] - 2026-07-12

### Added
- `impact_analysis` tool: full transitive **multi-hop** downstream blast radius of a column,
  field, or table (every dependent field, plus affected sheets, dashboards, workbooks, and the
  de-duplicated owners to notify) — no longer leaves the recursion to the model.
- `search_content` tool: case-insensitive **substring** search across workbooks, datasources,
  tables (and optionally fields/columns), since the Metadata API filters are exact-match only.
- Read-only enforcement: `graphql_query` rejects `mutation`/`subscription` operations.

### Changed
- `graphql_query` flags `partial_results: true` with a `warning` when a query hits the
  ~20,000-node limit, instead of passing the truncation through silently.
- `search_content` adds an exact-match fast path (complete, instant) and reports per-type
  `scanned`/`total` coverage so partial substring scans are explicit.
- Fully typed: the package ships a verified PEP 561 `py.typed` marker and passes
  `mypy --strict` in CI, so consumers importing it get complete types.

### Internal
- CI now runs `ruff format --check` and `mypy --strict`, uploads coverage to Codecov
  (85% floor), and scans with CodeQL and OpenSSF Scorecard. GitHub Actions are pinned to
  commit SHAs; a tool-schema contract test guards the public tool API.
- Add an `mcp-name` marker to the README so the official MCP registry can validate
  package ownership for the PyPI listing.

## [0.1.0] - 2026-07-09

### Added
- Initial release: a read-only MCP server over the Tableau Metadata API (GraphQL).
- Five tools: `graphql_query`, `introspect_schema`, `lineage_examples`, `where_used`, `server_info`.
- Generic auth for Tableau **Server** and **Cloud** via Personal Access Token, with a
  cookie/token fallback for SSO tenants.
- Auto-detection of the REST API version (`/api/serverinfo`) and the GraphQL endpoint
  (`/api/metadata/graphql`, falling back to `/relationship-service-war/graphql`).
- Robust `where_used` resolution via core lineage (works without the Data Management add-on).
- Embedded schema cheat-sheet and 28 curated question→GraphQL examples across 8 categories.
- `uvx`-runnable console entry point; no runtime dependencies beyond the MCP SDK.

[Unreleased]: https://github.com/tdries/tableau-graphQL-mcp/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/tdries/tableau-graphQL-mcp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/tdries/tableau-graphQL-mcp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/tdries/tableau-graphQL-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/tdries/tableau-graphQL-mcp/releases/tag/v0.1.0
