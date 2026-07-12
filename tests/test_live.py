"""Opt-in live smoke test against a real Tableau site. Skipped unless TABLEAU_LIVE is set.

Run it locally against your own site (never wire secrets into public CI):

    TABLEAU_LIVE=1 TABLEAU_SERVER=... TABLEAU_SITE_CONTENT_URL=... \
    TABLEAU_PAT_NAME=... TABLEAU_PAT_SECRET=... uv run pytest -m live
"""

import os

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.getenv("TABLEAU_LIVE"),
        reason="set TABLEAU_LIVE=1 (with real Tableau credentials in the env) to run",
    ),
]


def test_server_info_reports_connection():
    from tableau_graphql_mcp import server

    info = server.server_info()
    assert info.get("server")
    assert "catalog_available" in info


def test_typename_probe():
    from tableau_graphql_mcp import server

    resp = server.graphql_query("{ __typename }")
    assert resp["data"]["__typename"] == "Query"
