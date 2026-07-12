# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/). Note that the **tool schema is the public
API**: renaming a tool or a required argument is a MAJOR change.

## [Unreleased]

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

[Unreleased]: https://github.com/tdries/tableau-graphQL-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tdries/tableau-graphQL-mcp/releases/tag/v0.1.0
