"""Tool-level tests: exercise each @mcp.tool through a fake client (no network)."""

import pytest

from tableau_graphql_mcp import server


class FakeClient:
    def __init__(self, resp=None, info=None):
        self.resp = resp if resp is not None else {"data": {"ok": 1}}
        self.info = info or {"server": "x", "catalog_available": True}
        self.queries = []

    def graphql(self, query, variables=None):
        self.queries.append((query, variables))
        return self.resp

    def server_info(self):
        return self.info


def _use(monkeypatch, fake):
    monkeypatch.setattr(server, "_client", fake)


def test_graphql_query_passthrough(monkeypatch):
    _use(monkeypatch, FakeClient({"data": {"n": 1}}))
    assert server.graphql_query("{ x }")["data"]["n"] == 1


def test_graphql_query_rejects_writes():
    with pytest.raises(server.TableauError):
        server.graphql_query("mutation { doThing }")


def test_graphql_query_flags_partial(monkeypatch):
    _use(monkeypatch, FakeClient({"data": {}, "errors": [{"extensions": {"code": "NODE_LIMIT_EXCEEDED"}}]}))
    r = server.graphql_query("{ x }")
    assert r["partial_results"] is True
    assert "PARTIAL" in r["warning"]


def test_introspect_schema_type(monkeypatch):
    fake = FakeClient({"data": {"__type": {"name": "Column"}}})
    _use(monkeypatch, fake)
    assert server.introspect_schema("Column")["data"]["__type"]["name"] == "Column"
    assert fake.queries[-1][1] == {"n": "Column"}


def test_introspect_schema_root(monkeypatch):
    _use(monkeypatch, FakeClient({"data": {"__schema": {}}}))
    assert "__schema" in server.introspect_schema()["data"]


def test_lineage_examples_all():
    r = server.lineage_examples()
    assert r["examples"]
    assert "schema_cheatsheet" in r


def test_lineage_examples_unknown_category():
    assert "error" in server.lineage_examples("nope")


def test_where_used_splits_csv(monkeypatch):
    _use(monkeypatch, FakeClient({"data": {"columns": [], "fields": [], "databaseTables": []}}))
    assert isinstance(server.where_used("A, B"), dict)


def test_where_used_empty_raises():
    with pytest.raises(server.TableauError):
        server.where_used([])


def test_impact_analysis_tool(monkeypatch):
    _use(monkeypatch, FakeClient({"data": {"columns": [], "fields": [], "databaseTables": []}}))
    assert server.impact_analysis("X")["found"] is False


def test_impact_analysis_empty_raises():
    with pytest.raises(server.TableauError):
        server.impact_analysis("   ")


def test_search_content_tool(monkeypatch):
    _use(monkeypatch, FakeClient({"data": {}}))
    assert "matches" in server.search_content("term", types=["workbook"])


def test_search_content_empty_raises():
    with pytest.raises(server.TableauError):
        server.search_content("  ")


def test_server_info_tool(monkeypatch):
    _use(monkeypatch, FakeClient(info={"server": "x", "catalog_available": True}))
    assert server.server_info()["catalog_available"] is True
