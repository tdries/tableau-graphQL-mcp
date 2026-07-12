import pytest

from tableau_graphql_mcp.config import Settings, normalize_server


def test_normalize_server():
    assert normalize_server("tableau.company.com") == "https://tableau.company.com"
    assert normalize_server("https://x.online.tableau.com/") == "https://x.online.tableau.com"
    assert normalize_server("https://h.com/foo/bar") == "https://h.com"
    assert normalize_server("http://h:8000/") == "http://h:8000"


def test_from_env_pat_keeps_secret_intact():
    s = Settings.from_env(
        {
            "TABLEAU_SERVER": "https://h.com",
            "TABLEAU_PAT_NAME": "n",
            "TABLEAU_PAT_SECRET": "abc==:def",  # secrets can contain ':', must not be split
        }
    )
    assert s.server == "https://h.com"
    assert s.pat_name == "n"
    assert s.pat_secret == "abc==:def"
    assert s.site_content_url == ""


def test_missing_server_raises():
    with pytest.raises(RuntimeError):
        Settings.from_env({})


def test_missing_auth_raises():
    with pytest.raises(RuntimeError):
        Settings.from_env({"TABLEAU_SERVER": "https://h.com"})


def test_cookie_auth_is_valid():
    s = Settings.from_env({"TABLEAU_SERVER": "https://h.com", "TABLEAU_COOKIE": "workgroup_session_id=x"})
    assert s.cookie == "workgroup_session_id=x"
