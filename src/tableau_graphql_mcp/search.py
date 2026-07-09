"""search_content: case-insensitive SUBSTRING discovery across asset types.

The Metadata API's own filters are exact and case-sensitive, so partial-name search means
paging a connection and matching client-side. This scans up to a bounded number of pages per
type and reports when it stops, so results are never silently truncated.
"""

from __future__ import annotations

from .client import TableauClient, TableauError

# type -> (connection field, node selection, formatter)
TYPE_SPECS = {
    "workbook": ("workbooksConnection", "name projectName owner { username }",
                 lambda n: {"name": n["name"], "project": n.get("projectName"),
                            "owner": (n.get("owner") or {}).get("username")}),
    "datasource": ("publishedDatasourcesConnection", "name projectName isCertified owner { username }",
                   lambda n: {"name": n["name"], "project": n.get("projectName"),
                              "certified": n.get("isCertified"), "owner": (n.get("owner") or {}).get("username")}),
    "table": ("databaseTablesConnection", "name schema database { name }",
              lambda n: {"name": n["name"], "schema": n.get("schema"),
                         "database": (n.get("database") or {}).get("name")}),
    "field": ("fieldsConnection", "name __typename",
              lambda n: {"name": n["name"], "type": n.get("__typename")}),
    "column": ("columnsConnection", "name table { __typename ... on DatabaseTable { name schema } }",
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
    truncated = []
    for t in types:
        conn_field, selection, fmt = TYPE_SPECS[t]
        found, after, pages, hit_cap = [], None, 0, False
        while True:
            q = (f"query($first:Int!,$after:String){{ {conn_field}(first:$first, after:$after)"
                 f"{{ nodes{{ {selection} }} pageInfo{{ hasNextPage endCursor }} }} }}")
            d = client.graphql(q, {"first": page_size, "after": after})
            conn = ((d.get("data") or {}).get(conn_field)) or {}
            for node in conn.get("nodes") or []:
                if node.get("name") and term_l in node["name"].lower():
                    found.append(fmt(node))
            pages += 1
            info = conn.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                break
            if pages >= max_pages:
                hit_cap = True
                break
            after = info["endCursor"]
        matches[t] = found
        if hit_cap:
            truncated.append(t)

    out = {
        "term": term,
        "matches": matches,
        "summary": {t: len(v) for t, v in matches.items()},
    }
    if truncated:
        out["truncated"] = truncated
        out["note"] = (f"Stopped after scanning ~{page_size * max_pages} items for: {', '.join(truncated)}. "
                       "Results may be incomplete on a large site; use graphql_query with an exact name for the full set.")
    return out
