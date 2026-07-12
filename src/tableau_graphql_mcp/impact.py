"""impact_analysis: full transitive (multi-hop) downstream lineage.

Given a column, field, or table, returns the COMPLETE blast radius: every field that
directly or indirectly depends on it, and all sheets, dashboards, workbooks, and owners
affected, walked transitively by Tableau's own ``downstream*`` edges (so a calc-of-a-calc
three hops away is included, not just direct references).

This complements ``where_used`` (which is a single, always-available core-lineage hop):
``impact_analysis`` gives depth, and derives workbooks from ``downstreamSheets.workbook``
because the flat ``downstreamWorkbooks`` edge is unreliable on some servers.
"""

from __future__ import annotations

from .client import TableauClient

# transitive downstream selection (valid on Column and on the Field types)
_DOWN = """
    downstreamFields { name __typename }
    downstreamSheets { name workbook { name projectName owner { username } } }
    downstreamDashboards { name workbook { name projectName owner { username } } }
    downstreamWorkbooks { name projectName owner { username } }
    downstreamOwners { username name email }
"""
# DatabaseTable has no downstreamFields; the rest apply.
_DOWN_TABLE = """
    downstreamSheets { name workbook { name projectName owner { username } } }
    downstreamDashboards { name workbook { name projectName owner { username } } }
    downstreamWorkbooks { name projectName owner { username } }
    downstreamOwners { username name email }
"""


def _node_limit_hit(resp: dict) -> bool:
    for e in resp.get("errors") or []:
        blob = f"{(e.get('extensions') or {}).get('code')} {e.get('message', '')}"
        if "NODE_LIMIT" in blob:
            return True
    return False


def impact_analysis(client: TableauClient, name: str) -> dict:
    cls = client.graphql(
        "query($n:String!){ columns(filter:{name:$n}){ __typename } "
        "fields(filter:{name:$n}){ __typename } "
        "databaseTables(filter:{name:$n}){ __typename } }",
        {"n": name},
    )
    d = cls.get("data") or {}
    kinds = [
        k
        for k, present in (
            ("column", d.get("columns")),
            ("field", d.get("fields")),
            ("table", d.get("databaseTables")),
        )
        if present
    ]
    if not kinds:
        return {
            "name": name,
            "found": False,
            "note": "No column, field, or table with that exact, case-sensitive name. "
            "Use search_content for substring matches.",
        }

    fields: dict = {}  # (name, type) -> True
    sheets: dict = {}  # (sheet, workbook) -> True
    dashboards: dict = {}  # (dashboard, workbook) -> True
    workbooks: dict = {}  # name -> {project, owner}
    owners: dict = {}  # username -> email
    truncated = False

    def add_wb(wb: dict):
        if wb and wb.get("name"):
            workbooks[wb["name"]] = {
                "project": wb.get("projectName"),
                "owner": (wb.get("owner") or {}).get("username"),
            }
            o = wb.get("owner") or {}
            if o.get("username"):
                owners.setdefault(o["username"], o.get("email"))

    def absorb(node: dict):
        for f in node.get("downstreamFields") or []:
            if f.get("name"):
                fields[(f["name"], f.get("__typename"))] = True
        for s in node.get("downstreamSheets") or []:
            wb = s.get("workbook") or {}
            if s.get("name"):
                sheets[(s["name"], wb.get("name"))] = True
            add_wb(wb)
        for db in node.get("downstreamDashboards") or []:
            wb = db.get("workbook") or {}
            if db.get("name"):
                dashboards[(db["name"], wb.get("name"))] = True
            add_wb(wb)
        for wb in node.get("downstreamWorkbooks") or []:
            add_wb(wb)
        for o in node.get("downstreamOwners") or []:
            if o.get("username"):
                owners.setdefault(o["username"], o.get("email"))

    def run(query: str, extract):
        nonlocal truncated
        r = client.graphql(query, {"n": name})
        if _node_limit_hit(r):
            truncated = True
        for node in extract(r.get("data") or {}):
            absorb(node)

    if "column" in kinds:
        run(
            f"query($n:String!){{ columns(filter:{{name:$n}}){{ name {_DOWN} }} }}",
            lambda data: data.get("columns") or [],
        )
    if "field" in kinds:
        run(
            f"query($n:String!){{ fields(filter:{{name:$n}}){{ __typename {_DOWN} }} }}",
            lambda data: data.get("fields") or [],
        )
    if "table" in kinds:
        run(
            f"query($n:String!){{ databaseTables(filter:{{name:$n}}){{ name {_DOWN_TABLE} }} }}",
            lambda data: data.get("databaseTables") or [],
        )

    return {
        "name": name,
        "found": True,
        "matched_as": kinds,
        "summary": {
            "affected_fields": len(fields),
            "affected_sheets": len(sheets),
            "affected_dashboards": len(dashboards),
            "affected_workbooks": len(workbooks),
            "owners_to_notify": len(owners),
        },
        "affected_fields": [{"name": n, "type": t} for (n, t) in sorted(fields)],
        "affected_workbooks": [{"name": n, **v} for n, v in sorted(workbooks.items())],
        "affected_dashboards": sorted({db for (db, _wb) in dashboards}),
        "owners_to_notify": [{"username": u, "email": e} for u, e in sorted(owners.items())],
        "note": (
            "Full transitive (multi-hop) downstream closure via Tableau's downstream lineage "
            "(calc-of-a-calc chains included). Workbooks are derived from downstream sheets/dashboards "
            "because the flat downstreamWorkbooks edge is unreliable. "
            + (
                "Some branches hit the ~20000-node limit and are incomplete; re-run on a narrower name. "
                if truncated
                else ""
            )
            + "If everything is empty on a site without Data Management, the transitive edges may not be "
            "indexed; fall back to where_used for the direct (one-hop) references."
        ),
        "truncated": truncated,
    }
