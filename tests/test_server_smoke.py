import pytest


def test_import_and_tools_present():
    from tableau_graphql_mcp import server
    for name in ("graphql_query", "introspect_schema", "lineage_examples", "where_used", "server_info"):
        assert callable(getattr(server, name))


def test_client_requires_env(monkeypatch):
    from tableau_graphql_mcp import server
    server._client = None
    for var in ("TABLEAU_SERVER", "TABLEAU_PAT_NAME", "TABLEAU_PAT_SECRET", "TABLEAU_COOKIE", "TABLEAU_AUTH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError):
        server.client()


def test_lineage_examples_filter():
    from tableau_graphql_mcp import server
    out = server.lineage_examples("impact")
    assert out["examples"]
    assert all(e["category"] == "impact" for e in out["examples"])


def test_write_guard():
    from tableau_graphql_mcp.server import _is_write
    assert _is_write("mutation { updateWorkbook }")
    assert _is_write("query Q { a } mutation M { b }")
    assert _is_write("subscription { onChange }")
    # not writes:
    assert not _is_write("{ workbooks { name } }")
    assert not _is_write('query Find { columns(filter: { name: "mutation" }) { name } }')
    assert not _is_write("query { mutationRate }")  # field named like a write, not an operation


def test_graphql_query_rejects_writes():
    from tableau_graphql_mcp import server
    from tableau_graphql_mcp.client import TableauError
    with pytest.raises(TableauError):
        server.graphql_query("mutation { deleteEverything }")
