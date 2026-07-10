"""search_content: find content by name.

The Metadata API's filters are exact and case-sensitive, so this does two things per type:
1. an EXACT-match fast path (one filtered query, always complete, instant even on huge sites), and
2. a bounded SUBSTRING scan (pages a connection client-side), reporting `scanned` vs `total`
   coverage so partial results are explicit rather than silently truncated.
"""

from __future__ import annotations

from .client import TableauClient, TableauError

# type -> (connection field, exact entry point, node selection, formatter)
TYPE_SPECS = {
    "workbook": ("workbooksConnection", "workbooks", "name projectName owner { username }",
                 lambda n: {"name": n["name"], "project": n.get("projectName"),
                            "owner": (n.get("owner") or {}).get("username")}),
    "datasource": ("publishedDatasourcesConnection", "publishedDatasources",
                   "name projectName isCertified owner { username }",
                   lambda n: {"name": n["name"], "project": n.get("projectName"),
                              "certified": n.get("isCertified"), "owner": (n.get("owner") or {}).get("username")}),
    "table": ("databaseTablesConnection", "databaseTables", "name schema database { name }",
              lambda n: {"name": n["name"], "schema": n.get("schema"),
                         "database": (n.get("database") or {}).get("name")}),
    "field": ("fieldsConnection", "fields", "name __typename",
              lambda n: {"name": n["name"], "type": n.get("__typename")}),
    "column": ("columnsConnection", "columns", "name table { __typename ... on DatabaseTable { name schema } }",
               lambda n: {"name": n["name"], "table": (n.get("table") or {}).get("name")}),
}
DEFAULT_TYPES = ["workbook", "datasource", "table"]


def search_content(client: TableauClient, term: str, types: list[str] | None = None,
                   page_size: int = 200, max_pages: int = 6) -> dict:
    term_l = term.lower()
    types = types or DEFAULT_TYPES
    unknown = [t for t in types if t not in TYPE_SPECS]
    if unknown:
        raise TableauError(f"Unknown type(s) {unknown}. Choose from: {list(TYPE_SPECS)}.")

    matches: dict[str, list] = {}
    coverage: dict[str, dict] = {}
    for t in types:
        conn_field, exact_entry, selection, fmt = TYPE_SPECS[t]

        # 1) exact-match fast path: always complete, one filtered query
        exact = client.graphql(f"query($t:String!){{ {exact_entry}(filter:{{name:$t}}){{ {selection} }} }}", {"t": term})
        found, seen = [], set()
        for n in ((exact.get("data") or {}).get(exact_entry) or []):
            if n.get("name") and n["name"] not in seen:
                seen.add(n["name"])
                found.append({**fmt(n), "exact": True})

        # 2) bounded substring scan with coverage
        after, pages, scanned, total, hit_cap = None, 0, 0, None, False
        while True:
            d = client.graphql(
                f"query($first:Int!,$after:String){{ {conn_field}(first:$first, after:$after)"
                f"{{ nodes{{ {selection} }} pageInfo{{ hasNextPage endCursor }} totalCount }} }}",
                {"first": page_size, "after": after})
            conn = ((d.get("data") or {}).get(conn_field)) or {}
            if total is None:
                total = conn.get("totalCount")
            nodes = conn.get("nodes") or []
            scanned += len(nodes)
            for n in nodes:
                if n.get("name") and term_l in n["name"].lower() and n["name"] not in seen:
                    seen.add(n["name"])
                    found.append({**fmt(n), "exact": False})
            pages += 1
            info = conn.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                break
            if pages >= max_pages:
                hit_cap = True
                break
            after = info["endCursor"]

        matches[t] = found
        coverage[t] = {"scanned": scanned, "total": total,
                       "substring_complete": (not hit_cap and (total is None or scanned >= total))}

    incomplete = [t for t, c in coverage.items() if not c["substring_complete"]]
    return {
        "term": term,
        "matches": matches,
        "coverage": coverage,
        "summary": {t: len(v) for t, v in matches.items()},
        "note": ("Exact-name matches (\"exact\": true) are complete. Substring matches are bounded by the scan; "
                 "see `coverage` per type."
                 + (f" Incomplete substring scan for: {', '.join(incomplete)} (scanned < total)." if incomplete else "")),
    }
