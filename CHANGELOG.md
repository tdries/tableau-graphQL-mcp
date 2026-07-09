# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/). Note that the **tool schema is the public
API**: renaming a tool or a required argument is a MAJOR change.

## [Unreleased]

### Added
- `search_content` tool: case-insensitive **substring** search across workbooks, datasources,
  tables (and optionally fields/columns), since the Metadata API filters are exact-match only.
- Read-only enforcement: `graphql_query` rejects `mutation`/`subscription` operations.

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
