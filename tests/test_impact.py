from tableau_graphql_mcp.impact import impact_analysis


class FakeClient:
    """Classify query -> column; seed query -> a transitive downstream closure."""

    def graphql(self, query, variables=None):
        if "downstreamFields" in query:
            return {"data": {"columns": [{
                "name": "BASE",
                "downstreamFields": [{"name": "Calc A", "__typename": "CalculatedField"},
                                     {"name": "Calc B", "__typename": "CalculatedField"}],
                "downstreamSheets": [{"name": "S1", "workbook": {"name": "WB1", "projectName": "P",
                                                                 "owner": {"username": "u1"}}}],
                "downstreamDashboards": [{"name": "D1", "workbook": {"name": "WB1"}}],
                "downstreamWorkbooks": [],
                "downstreamOwners": [{"username": "u2", "email": "u2@example.com"}],
            }]}}
        return {"data": {"columns": [{"__typename": "Column"}], "fields": [], "databaseTables": []}}


def test_impact_transitive_closure():
    r = impact_analysis(FakeClient(), "BASE")
    assert r["found"] and r["matched_as"] == ["column"]
    assert {f["name"] for f in r["affected_fields"]} == {"Calc A", "Calc B"}   # multi-hop set
    assert r["summary"]["affected_fields"] == 2
    assert [w["name"] for w in r["affected_workbooks"]] == ["WB1"]             # derived from sheet + dashboard
    assert {o["username"] for o in r["owners_to_notify"]} == {"u1", "u2"}      # wb owner + downstreamOwners


def test_impact_not_found():
    class Empty:
        def graphql(self, q, v=None):
            return {"data": {"columns": [], "fields": [], "databaseTables": []}}
    assert impact_analysis(Empty(), "nope")["found"] is False
