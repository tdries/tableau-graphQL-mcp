import pytest

from tableau_graphql_mcp.client import TableauError
from tableau_graphql_mcp.search import search_content


class PagedClient:
    """Serves the exact-match query, then two connection pages (only 'workbook' searched)."""

    def __init__(self):
        self.page = 0

    def graphql(self, query, variables=None):
        if "Connection(" not in query:  # exact-match fast path
            return {"data": {"workbooks": [
                {"name": "Sales Overview", "projectName": "Analytics", "owner": {"username": "jane.doe"}}]}}
        self.page += 1
        if self.page == 1:
            return {"data": {"workbooksConnection": {
                "nodes": [{"name": "Sales Overview", "projectName": "Analytics", "owner": {"username": "jane.doe"}},
                          {"name": "HR Report", "projectName": "People", "owner": {"username": "x"}}],
                "pageInfo": {"hasNextPage": True, "endCursor": "c1"}, "totalCount": 3}}}
        return {"data": {"workbooksConnection": {
            "nodes": [{"name": "Regional Sales", "projectName": "Analytics", "owner": {"username": "jane.doe"}}],
            "pageInfo": {"hasNextPage": False}, "totalCount": 3}}}


def test_exact_and_substring_across_pages():
    out = search_content(PagedClient(), "sales", types=["workbook"])
    hits = out["matches"]["workbook"]
    names = {h["name"] for h in hits}
    assert names == {"Sales Overview", "Regional Sales"}      # both pages, case-insensitive
    assert {h["name"] for h in hits if h["exact"]} == {"Sales Overview"}   # exact fast path flagged
    assert out["summary"]["workbook"] == 2


def test_coverage_reported():
    out = search_content(PagedClient(), "sales", types=["workbook"])
    cov = out["coverage"]["workbook"]
    assert cov["total"] == 3 and cov["scanned"] == 3 and cov["substring_complete"] is True


def test_unknown_type_raises():
    with pytest.raises(TableauError):
        search_content(PagedClient(), "x", types=["bogus"])
