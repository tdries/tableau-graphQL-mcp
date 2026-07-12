"""Transport/auth tests with a mocked urllib layer (no network)."""

import io
import json
import urllib.error
import urllib.request

import pytest

from tableau_graphql_mcp.client import TableauClient, TableauError
from tableau_graphql_mcp.config import Settings


class _Resp:
    def __init__(self, body):
        self._b = json.dumps(body).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _httperr(url, code, body=b"err"):
    return urllib.error.HTTPError(url, code, "error", {}, io.BytesIO(body))


def _patch(monkeypatch, handler):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: handler(req))


def _client(**env):
    base = {"TABLEAU_SERVER": "https://h.com", "TABLEAU_PAT_NAME": "n", "TABLEAU_PAT_SECRET": "sec"}
    base.update(env)
    return TableauClient(Settings.from_env(base))


def test_api_version_from_serverinfo(monkeypatch):
    _patch(monkeypatch, lambda req: _Resp({"serverInfo": {"restApiVersion": "3.25"}}))
    assert _client().api_version() == "3.25"


def test_api_version_fallback_on_404(monkeypatch):
    def h(req):
        raise _httperr(req.full_url, 404)

    _patch(monkeypatch, h)
    assert _client().api_version() == "3.4"


def test_signin_returns_and_caches_token(monkeypatch):
    calls = {"signin": 0}

    def h(req):
        if "serverinfo" in req.full_url:
            return _Resp({"serverInfo": {"restApiVersion": "3.4"}})
        if "auth/signin" in req.full_url:
            calls["signin"] += 1
            body = json.loads(req.data)
            assert body["credentials"]["personalAccessTokenName"] == "n"
            assert body["credentials"]["personalAccessTokenSecret"] == "sec"  # never split
            return _Resp({"credentials": {"token": "TOK", "site": {"id": "s1"}}})
        raise AssertionError(req.full_url)

    _patch(monkeypatch, h)
    c = _client()
    assert c._get_token() == "TOK"
    assert c._get_token() == "TOK"  # cached
    assert calls["signin"] == 1


def test_signin_401_raises_with_hint(monkeypatch):
    def h(req):
        if "serverinfo" in req.full_url:
            return _Resp({"serverInfo": {"restApiVersion": "3.4"}})
        raise _httperr(req.full_url, 401, b'{"error":"bad"}')

    _patch(monkeypatch, h)
    with pytest.raises(TableauError) as e:
        _client()._get_token()
    assert "SSO" in str(e.value) or "PAT" in str(e.value)


def test_auth_headers_cookie_derives_xsrf():
    c = _client(TABLEAU_COOKIE="workgroup_session_id=abc; XSRF-TOKEN=xyz; other=1")
    h = c._auth_headers()
    assert h["Cookie"].startswith("workgroup_session_id=abc")
    assert h["X-XSRF-TOKEN"] == "xyz"
    assert h["Referer"].endswith("/metadata/graphiql/")


def test_auth_headers_preset_token():
    c = _client(TABLEAU_AUTH_TOKEN="PRE")
    assert c._auth_headers() == {"X-Tableau-Auth": "PRE"}


def test_resolve_endpoint_standard(monkeypatch):
    c = _client(TABLEAU_AUTH_TOKEN="PRE")
    _patch(
        monkeypatch,
        lambda req: (
            _Resp({"data": {"__typename": "Query"}})
            if req.full_url.endswith("/api/metadata/graphql")
            else (_ for _ in ()).throw(AssertionError(req.full_url))
        ),
    )
    assert c._resolve_endpoint().endswith("/api/metadata/graphql")


def test_resolve_endpoint_fallback_on_404(monkeypatch):
    c = _client(TABLEAU_AUTH_TOKEN="PRE")

    def h(req):
        if req.full_url.endswith("/api/metadata/graphql"):
            raise _httperr(req.full_url, 404)
        return _Resp({"data": {"__typename": "Query"}})

    _patch(monkeypatch, h)
    assert c._resolve_endpoint().endswith("/relationship-service-war/graphql")


def test_resolve_endpoint_400_is_live(monkeypatch):
    c = _client(TABLEAU_AUTH_TOKEN="PRE")
    _patch(monkeypatch, lambda req: (_ for _ in ()).throw(_httperr(req.full_url, 400)))
    assert c._resolve_endpoint().endswith("/api/metadata/graphql")


def test_graphql_success(monkeypatch):
    c = _client(TABLEAU_AUTH_TOKEN="PRE")
    c._endpoint = "https://h.com/api/metadata/graphql"
    _patch(monkeypatch, lambda req: _Resp({"data": {"ok": 1}}))
    assert c.graphql("{ x }")["data"]["ok"] == 1


def test_graphql_refreshes_token_on_401(monkeypatch):
    c = _client()
    c._endpoint = "https://h.com/api/metadata/graphql"
    c._api_version = "3.4"
    posts = {"n": 0}

    def h(req):
        if "auth/signin" in req.full_url:
            return _Resp({"credentials": {"token": "NEW", "site": {"id": "s"}}})
        posts["n"] += 1
        if posts["n"] == 1:
            raise _httperr(req.full_url, 401)
        return _Resp({"data": {"ok": 1}})

    _patch(monkeypatch, h)
    assert c.graphql("{ x }")["data"]["ok"] == 1


def test_graphql_error_raises(monkeypatch):
    c = _client(TABLEAU_AUTH_TOKEN="PRE")
    c._endpoint = "https://h.com/api/metadata/graphql"
    _patch(monkeypatch, lambda req: (_ for _ in ()).throw(_httperr(req.full_url, 500)))
    with pytest.raises(TableauError):
        c.graphql("{ x }")


def test_server_info(monkeypatch):
    c = _client(TABLEAU_AUTH_TOKEN="PRE")

    def h(req):
        if "serverinfo" in req.full_url:
            return _Resp({"serverInfo": {"productVersion": {"value": "2025.1.8"}, "restApiVersion": "3.25"}})
        return _Resp({"data": {"__typename": "Query", "databaseTablesConnection": {"totalCount": 42}}})

    _patch(monkeypatch, h)
    info = c.server_info()
    assert info["server"] == "https://h.com"
    assert info["product_version"] == "2025.1.8"
    assert info["catalog_available"] is True
    assert info["database_tables_visible"] == 42


def test_signout_clears_token(monkeypatch):
    c = _client()
    c._token = "T"
    c._api_version = "3.4"
    _patch(monkeypatch, lambda req: _Resp({}))
    c.signout()
    assert c._token is None
