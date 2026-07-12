"""The ``where_used`` resolver: exact names (columns, fields, tables) -> the workbooks
and published datasources that consume them.

Uses CORE lineage (referencedByFields -> field.sheets -> workbook, and
field.datasource -> embedded datasource -> workbook), so it works without the Data
Management add-on, where ``downstreamWorkbooks`` is typically empty.
"""

from __future__ import annotations

from .client import TableauClient, TableauError

WHERE_USED_QUERY = """
query WhereUsed($names: [String]) {
  columns(filter: { nameWithin: $names }) {
    name
    table {
      __typename
      ... on DatabaseTable { name schema fullName database { name connectionType } }
      ... on CustomSQLTable { name database { name connectionType } }
    }
    referencedByFields {
      name
      datasource {
        __typename
        ... on EmbeddedDatasource { workbook { name projectName owner { username } } }
        ... on PublishedDatasource { name }
      }
      sheets { name workbook { name } }
    }
  }
  fields(filter: { nameWithin: $names }) {
    name
    __typename
    datasource {
      __typename
      ... on EmbeddedDatasource { workbook { name projectName owner { username } } }
      ... on PublishedDatasource { name }
    }
    sheets { name workbook { name } }
    ... on ColumnField { columns { name table { __typename ... on DatabaseTable { name schema } ... on CustomSQLTable { name } } } }
    ... on CalculatedField { formula }
  }
  databaseTables(filter: { nameWithin: $names }) {
    name
    schema
    fullName
    database { name connectionType }
    columns {
      name
      referencedByFields {
        name
        datasource {
          __typename
          ... on EmbeddedDatasource { workbook { name projectName owner { username } } }
          ... on PublishedDatasource { name }
        }
        sheets { name workbook { name } }
      }
    }
  }
}
"""


def _table_info(tbl: dict | None) -> dict:
    tbl = tbl or {}
    db = tbl.get("database") or {}
    return {
        "table": tbl.get("name"),
        "schema": tbl.get("schema") or None,
        "database": db.get("name"),
        "connection": db.get("connectionType"),
        "custom_sql": tbl.get("__typename") == "CustomSQLTable",
    }


def _target(ds: dict | None):
    ds = ds or {}
    kind = ds.get("__typename")
    if kind == "EmbeddedDatasource":
        wb = ds.get("workbook") or {}
        if wb.get("name"):
            return ("workbook", wb["name"], wb.get("projectName"), (wb.get("owner") or {}).get("username"))
    if kind == "PublishedDatasource" and ds.get("name"):
        return ("datasource", ds["name"], "Published datasource", None)
    return None


def where_used(client: TableauClient, names: list[str]) -> dict:
    """Resolve which workbooks / datasources use the given exact names."""
    resp = client.graphql(WHERE_USED_QUERY, {"names": names})
    data = resp.get("data") or {}
    if resp.get("errors") and not data:
        raise TableauError("Metadata API errors: " + str(resp["errors"])[:400])

    items: dict[tuple, dict] = {}

    def rec(target) -> dict:
        kind, name, project, owner = target
        r = items.get((kind, name))
        if not r:
            r = items[(kind, name)] = {
                "kind": kind,
                "name": name,
                "project": project,
                "owner": owner,
                "via": [],
                "_seen": set(),
                "_tables": {},
                "sheets": set(),
            }
        if project and not r["project"]:
            r["project"] = project
        if owner and not r["owner"]:
            r["owner"] = owner
        return r

    def add_field(field: dict, via: dict):
        sheets_by_wb: dict[str, set] = {}
        for s in field.get("sheets") or []:
            wn = (s.get("workbook") or {}).get("name")
            if wn and s.get("name"):
                sheets_by_wb.setdefault(wn, set()).add(s["name"])
        tgt = _target(field.get("datasource"))
        targets = [tgt] if tgt else [("workbook", wn, None, None) for wn in sheets_by_wb]
        key = (via.get("kind"), via.get("name"), via.get("table_key"))
        for t in targets:
            r = rec(t)
            if key not in r["_seen"]:
                r["_seen"].add(key)
                r["via"].append({k: v for k, v in via.items() if k != "table_key"})
            for sn in sheets_by_wb.get(r["name"], set()):
                r["sheets"].add(sn)

    # column matches -> the fields that reference them
    for c in data.get("columns") or []:
        tinfo = _table_info(c.get("table"))
        for rf in c.get("referencedByFields") or []:
            add_field(
                rf,
                {
                    "kind": "column",
                    "name": c["name"],
                    "table": tinfo,
                    "alias": rf.get("name"),
                    "table_key": tinfo.get("table"),
                },
            )

    # field / alias matches
    for f in data.get("fields") or []:
        cols = [
            {"name": col.get("name"), "table": _table_info(col.get("table"))}
            for col in f.get("columns") or []
        ]
        add_field(
            f,
            {
                "kind": "field",
                "name": f["name"],
                "field_type": f.get("__typename"),
                "columns": cols,
                "table_key": None,
            },
        )

    # table matches -> its columns -> the fields that reference them (aggregate columns per workbook)
    for t in data.get("databaseTables") or []:
        tinfo = _table_info(t)
        tkey = tinfo.get("table")
        for c in t.get("columns") or []:
            cname = c.get("name")
            for rf in c.get("referencedByFields") or []:
                sheets_by_wb: dict[str, set] = {}
                for s in rf.get("sheets") or []:
                    wn = (s.get("workbook") or {}).get("name")
                    if wn and s.get("name"):
                        sheets_by_wb.setdefault(wn, set()).add(s["name"])
                tgt = _target(rf.get("datasource"))
                for target in [tgt] if tgt else [("workbook", wn, None, None) for wn in sheets_by_wb]:
                    r = rec(target)
                    tv = r["_tables"].get(tkey)
                    if not tv:
                        tv = {"kind": "table", "name": tinfo["table"], "table": tinfo, "columns": set()}
                        r["_tables"][tkey] = tv
                        r["via"].append(tv)
                    if cname:
                        tv["columns"].add(cname)
                    for sn in sheets_by_wb.get(r["name"], set()):
                        r["sheets"].add(sn)

    results = []
    for r in sorted(items.values(), key=lambda x: (x["kind"] != "workbook", x["name"].lower())):
        r.pop("_seen", None)
        r.pop("_tables", None)
        for via in r["via"]:
            if via.get("kind") == "table" and isinstance(via.get("columns"), set):
                via["columns"] = sorted(via["columns"])
        r["used_on_sheets"] = sorted(r.pop("sheets"))
        results.append(r)

    return {
        "searched": names,
        "results": results,
        "summary": {
            "workbooks": sum(1 for r in results if r["kind"] == "workbook"),
            "datasources": sum(1 for r in results if r["kind"] == "datasource"),
            "columns_matched": len(data.get("columns") or []),
            "fields_matched": len(data.get("fields") or []),
            "tables_matched": len(data.get("databaseTables") or []),
        },
        "note": "Resolved via core lineage (referencedByFields + field.sheets + datasource->workbook); "
        "reliable without the Data Management add-on. Names are matched exactly and case-sensitively.",
    }
