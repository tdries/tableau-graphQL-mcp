"""FastMCP server exposing the Tableau Metadata API (GraphQL) for lineage questions.

Read-only. Seven tools: a universal GraphQL passthrough, live schema introspection, a
curated query-example library, a robust ``where_used`` resolver, a multi-hop
``impact_analysis``, a substring ``search_content``, and a connection probe.
Works against any Tableau Server or Tableau Cloud site (see config.py for env vars).
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import TableauClient, TableauError
from .config import Settings
from .examples import CATEGORIES, EXAMPLES, SCHEMA_CHEATSHEET
from .impact import impact_analysis as _impact_analysis
from .lineage import where_used as _where_used
from .search import search_content as _search_content

# stdio transport: logs MUST go to stderr; stdout carries the JSON-RPC protocol.
logging.basicConfig(
    level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)

mcp = FastMCP("tableau-graphql")

_client: TableauClient | None = None


def client() -> TableauClient:
    """Build the Tableau client once (lazily, so listing tools never needs credentials)."""
    global _client
    if _client is None:
        _client = TableauClient(Settings.from_env())
    return _client


_WRITE_OP = re.compile(r"(?:^|})\s*(mutation|subscription)\b", re.IGNORECASE)


def _is_write(query: str) -> bool:
    """True if the document contains a mutation/subscription operation.

    Strips comments and string literals first so 'mutation' as a field value or
    name doesn't trip it. The Metadata API is query-only; this makes read-only
    true by construction rather than relying on the remote to reject writes.
    """
    q = re.sub(r"#[^\n]*", "", query)
    q = re.sub(r'"(?:[^"\\]|\\.)*"', '""', q)
    return bool(_WRITE_OP.search(q))


def _partial_results_warning(resp: dict[str, Any]) -> str | None:
    """Turn the Metadata API's partial-result errors into a loud, structured warning.

    The API returns partial `data` PLUS a NODE_LIMIT_EXCEEDED / MAX_PAGE_SIZE_EXCEEDED entry
    in `errors`; the model can miss that, so surface it as a top-level flag."""
    for e in resp.get("errors") or []:
        code = str((e.get("extensions") or {}).get("code") or "") + " " + str(e.get("message", ""))
        if "NODE_LIMIT" in code:
            return (
                "PARTIAL RESULTS: the query exceeded the ~20,000-node limit and Tableau returned only "
                "part of the graph. Do NOT treat this as complete. Narrow the filter, select fewer nested "
                "fields, or page the outer connection with first/after (or use where_used / search_content / "
                "impact_analysis, which page and bound results for you)."
            )
        if "MAX_PAGE_SIZE" in code:
            return "Page size was clamped to 1000 (MAX_PAGE_SIZE_EXCEEDED); request first:1000 and page with after."
    return None


@mcp.tool()
def graphql_query(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run ANY read-only GraphQL query against the Tableau Metadata API. This is the
    general-purpose tool; use it for any lineage question. Returns {"data": ..., "errors": ...}.

    The Metadata API is a GraphQL graph of Tableau content (workbooks, sheets, dashboards,
    datasources, fields) and, with the Data Management add-on, physical assets (databases,
    tables, columns) and their upstream/downstream lineage.

    How to write a correct query:
    - Filters are EXACT and case-sensitive: `filter: {name: "X"}` or `filter: {nameWithin: ["X","Y"]}`
      (nameWithin is the only multi/OR match; there is NO substring or regex).
    - Every list field has a `<name>Connection` variant with `first`/`offset`/`after` + `pageInfo`
      (page size max 1000). Keep one query under ~20,000 nodes; narrow filters and page.
    - Fields is an interface; branch with `__typename` and inline fragments
      (`... on ColumnField { columns { name } }`, `... on CalculatedField { formula }`).
    - Reach a field's owning workbook via `datasource { ... on EmbeddedDatasource { workbook { name } } }`.
    - `downstream*` fields (downstreamWorkbooks/Owners, external tables/columns) need Data Management
      (Tableau Catalog) and are often empty otherwise; then resolve via core lineage
      (referencedByFields -> sheets -> workbook), or just call the `where_used` tool.

    Entry points include: workbooks, sheets, dashboards, publishedDatasources, embeddedDatasources,
    fields, columnFields, calculatedFields, columns, databaseTables, customSQLTables, databases,
    flows, tableauUsers, dataQualityWarnings. Call `lineage_examples` for ready-made query templates
    and a schema cheat-sheet, or `introspect_schema` to inspect any type's exact fields.

    Read-only: mutation and subscription operations are rejected. If a query exceeds the
    ~20,000-node limit, the response is flagged with `partial_results: true` and a `warning`
    (it does NOT auto-page an arbitrary query) so you never mistake a truncated result for a
    complete one.
    """
    if _is_write(query):
        raise TableauError(
            "This server is read-only: mutation and subscription operations are not allowed "
            "(the Tableau Metadata API is query-only)."
        )
    resp = client().graphql(query, variables)
    warning = _partial_results_warning(resp)
    if warning:
        return {**resp, "partial_results": True, "warning": warning}
    return resp


@mcp.tool()
def introspect_schema(type_name: str | None = None) -> dict[str, Any]:
    """Introspect the live Metadata API GraphQL schema (introspection is enabled).

    With no argument: returns every Query entry point (with its args) and the full list of
    type names. With `type_name` (e.g. "Column", "Workbook", "DatabaseTable", "CalculatedField"):
    returns that type's fields, their result types, and args, so you can write a correct query
    against exactly what this server exposes.
    """
    if type_name:
        q = (
            "query($n:String!){ __type(name:$n){ name kind description "
            "fields{ name description args{ name } type{ name kind ofType{ name kind ofType{ name kind } } } } "
            "interfaces{ name } possibleTypes{ name } inputFields{ name } enumValues{ name } } }"
        )
        return client().graphql(q, {"n": type_name})
    q = (
        "{ __schema{ queryType{ fields{ name args{ name type{ name kind ofType{ name } } } } } "
        "types{ name kind } } }"
    )
    return client().graphql(q, {})


@mcp.tool()
def lineage_examples(category: str | None = None) -> dict[str, Any]:
    """Return a schema cheat-sheet and a library of curated lineage questions with their
    correct GraphQL queries (+ example variables). Read this before composing a `graphql_query`.

    Categories: impact, provenance, calc, datasource, search, inventory, governance, ownership.
    Pass one to filter; omit to get them all. Each example has: question, graphql, variables, notes.
    """
    if category:
        cat = category.strip().lower()
        examples = [e for e in EXAMPLES if e["category"] == cat]
        if not examples:
            return {"error": f"unknown category {category!r}", "categories": CATEGORIES}
    else:
        examples = EXAMPLES
    return {"schema_cheatsheet": SCHEMA_CHEATSHEET, "categories": CATEGORIES, "examples": examples}


@mcp.tool()
def where_used(names: list[str]) -> dict[str, Any]:
    """Find which workbooks (and published datasources) USE the given names, the common
    'where is this used / impact analysis' question, resolved robustly.

    `names` are EXACT, case-sensitive names of any of: a Snowflake/DB column, a Tableau
    field or alias, or a database table. Pass several to check them in one call. Results
    group by workbook, showing how each matched (column / field / whole table, with schema
    and source table) and which worksheets use it.

    This uses CORE lineage (referencedByFields -> field.sheets -> workbook, and
    field.datasource -> workbook), so it works even without the Data Management add-on where
    `downstreamWorkbooks` is empty. For other shapes of question, use `graphql_query`.
    """
    if isinstance(names, str):
        names = [n.strip() for n in names.split(",") if n.strip()]
    if not names:
        raise TableauError("Provide at least one exact name to look up.")
    return _where_used(client(), names)


@mcp.tool()
def impact_analysis(name: str) -> dict[str, Any]:
    """Full transitive (MULTI-HOP) downstream impact of a column, field, or table. Returns every
    field that directly OR indirectly depends on it, and all affected sheets, dashboards,
    workbooks, plus the de-duplicated set of OWNERS to notify before a change.

    This is the "what breaks if I change/drop this?" tool. Unlike `where_used` (one core-lineage
    hop), it follows the whole dependency chain — a calc built on a calc built on the column is
    included. `name` is exact and case-sensitive. Workbooks are derived from downstream
    sheets/dashboards (the flat downstreamWorkbooks edge is unreliable). If it returns nothing on a
    site without Data Management, the transitive lineage may not be indexed there — use `where_used`
    for the direct references.
    """
    if isinstance(name, str):
        name = name.strip()
    if not name:
        raise TableauError("Provide an exact column, field, or table name.")
    return _impact_analysis(client(), name)


@mcp.tool()
def search_content(term: str, types: list[str] | None = None) -> dict[str, Any]:
    """Find content whose NAME contains `term` (case-insensitive SUBSTRING). Use this when you
    only know part of a name, since every other tool and the Metadata API filter are exact-match.

    Searches workbooks, published datasources, and database tables by default. Pass `types` to
    choose from: "workbook", "datasource", "table", "field", "column". Returns matches grouped by
    type. It pages through content client-side, so on a very large site it scans the first ~1200
    of each type and says so in `note`; once you know the exact name, prefer `graphql_query` or `where_used`.
    """
    if isinstance(term, str):
        term = term.strip()
    if not term:
        raise TableauError("Provide a non-empty search term.")
    return _search_content(client(), term, types)


@mcp.tool()
def server_info() -> dict[str, Any]:
    """Report the connected Tableau environment: server URL, site, product & REST API version,
    which Metadata API endpoint is in use, the auth method, and whether external-asset
    (Data Management / Catalog) lineage appears available. Good first call to confirm the
    connection and understand what lineage depth to expect."""
    return client().server_info()


def main() -> None:
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
