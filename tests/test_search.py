import pytest

from tableau_graphql_mcp.client import TableauError
from tableau_graphql_mcp.search import search_content


class PagedClient:
    """Two pages of workbooks so paging + substring match are exercised (only 'workbook' is searched)."""

    def __init__(self):
        self.calls = 0

    def graphql(self, query, variables=None):
        self.calls += 1
        if self.calls == 1:
            return {"data": {"workbooksConnection": {
                "nodes": [{"name": "Sales Overview", "projectName": "Analytics", "owner": {"username": "jane.doe"}},
                          {"name": "HR Report", "projectName": "People", "owner": {"username": "x"}}],
                "pageInfo": {"hasNextPage": True, "endCursor": "c1"}}}}
        return {"data": {"workbooksConnection": {
            "nodes": [{"name": "Regional Sales", "projectName": "Analytics", "owner": {"username": "jane.doe"}}],
            "pageInfo": {"hasNextPage": False}}}}


def test_substring_match_across_pages():
    out = search_content(PagedClient(), "sales", types=["workbook"])
    names = {m["name"] for m in out["matches"]["workbook"]}
    assert names == {"Sales Overview", "Regional Sales"}   # both pages, case-insensitive
    assert "HR Report" not in names
    assert out["summary"]["workbook"] == 2


def test_unknown_type_raises():
    with pytest.raises(TableauError):
        search_content(PagedClient(), "x", types=["bogus"])
