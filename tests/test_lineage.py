from tableau_graphql_mcp.lineage import where_used


class FakeClient:
    """Returns canned Metadata API data so the resolver is testable offline."""

    def __init__(self, data):
        self._data = data

    def graphql(self, query, variables=None):
        return {"data": self._data}


def test_where_used_resolves_columns_and_tables():
    data = {
        "columns": [
            {
                "name": "SALES",
                "table": {"__typename": "DatabaseTable", "name": "T", "schema": "S",
                          "database": {"name": "DB", "connectionType": "snowflake"}},
                "referencedByFields": [
                    {
                        "name": "Sales Amount",
                        "datasource": {"__typename": "EmbeddedDatasource",
                                       "workbook": {"name": "WB1", "projectName": "P", "owner": {"username": "u"}}},
                        "sheets": [{"name": "Sheet A", "workbook": {"name": "WB1"}}],
                    }
                ],
            }
        ],
        "fields": [],
        "databaseTables": [
            {
                "name": "DIM_CUSTOMER", "schema": "SALES", "fullName": "SALES.DIM_CUSTOMER",
                "database": {"name": "DB", "connectionType": "snowflake"},
                "columns": [
                    {
                        "name": "C1",
                        "referencedByFields": [
                            {
                                "name": "f",
                                "datasource": {"__typename": "EmbeddedDatasource",
                                               "workbook": {"name": "WB2", "projectName": "P2", "owner": {"username": "u2"}}},
                                "sheets": [{"name": "S2", "workbook": {"name": "WB2"}}],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    out = where_used(FakeClient(data), ["SALES", "DIM_CUSTOMER"])

    names = {r["name"] for r in out["results"]}
    assert names == {"WB1", "WB2"}

    wb1 = next(r for r in out["results"] if r["name"] == "WB1")
    assert wb1["kind"] == "workbook"
    assert wb1["owner"] == "u"
    assert "Sheet A" in wb1["used_on_sheets"]
    assert wb1["via"][0]["kind"] == "column"
    assert wb1["via"][0]["table"]["schema"] == "S"

    wb2 = next(r for r in out["results"] if r["name"] == "WB2")
    assert wb2["via"][0]["kind"] == "table"
    assert wb2["via"][0]["columns"] == ["C1"]

    assert out["summary"]["workbooks"] == 2
    assert out["summary"]["datasources"] == 0


def test_where_used_published_datasource_target():
    data = {
        "columns": [],
        "fields": [
            {
                "name": "Amount",
                "__typename": "ColumnField",
                "datasource": {"__typename": "PublishedDatasource", "name": "Superstore"},
                "sheets": [],
                "columns": [{"name": "REVENUE", "table": {"__typename": "DatabaseTable", "name": "F", "schema": "V"}}],
            }
        ],
        "databaseTables": [],
    }
    out = where_used(FakeClient(data), ["Amount"])
    ds = out["results"][0]
    assert ds["kind"] == "datasource"
    assert ds["name"] == "Superstore"
    assert out["summary"]["datasources"] == 1
