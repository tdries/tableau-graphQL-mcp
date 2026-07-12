"""Transport + auth for the Tableau Metadata API (GraphQL), generic across Server and Cloud.

Stdlib only (urllib). Auth priority: a browser session cookie, then a pre-obtained
X-Tableau-Auth token, then a PAT sign-in (recommended). The REST API version and the
GraphQL endpoint path are auto-detected and cached.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import threading
import urllib.error
import urllib.request
from typing import Any

from .config import Settings

log = logging.getLogger("tableau-graphql-mcp")


class TableauError(RuntimeError):
    """A clean, model-readable error (no stack traces, no secrets)."""


class TableauClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self._lock = threading.Lock()
        self._token: str | None = settings.auth_token
        self._api_version: str | None = settings.api_version
        self._endpoint: str | None = None

    # ---------- low-level HTTP ----------
    def _request(
        self, url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        h = {"Accept": "application/json"}
        if data is not None:
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=h)
        with urllib.request.urlopen(req, timeout=self.s.timeout) as r:
            body = r.read()
        return json.loads(body) if body else {}

    @staticmethod
    def _http_message(e: urllib.error.HTTPError) -> str:
        try:
            detail = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            detail = ""
        return f"HTTP {e.code} {e.reason}. {detail}".strip()

    # ---------- REST API version ----------
    def api_version(self) -> str:
        if self._api_version:
            return self._api_version
        try:
            d = self._request(f"{self.s.server}/api/serverinfo")
            self._api_version = (d.get("serverInfo") or {}).get("restApiVersion") or "3.4"
        except Exception as exc:  # noqa: BLE001: any failure -> safe floor
            log.warning("serverinfo failed (%s); defaulting REST API version to 3.4", exc)
            self._api_version = "3.4"
        return self._api_version

    # ---------- auth ----------
    def _auth_headers(self) -> dict[str, str]:
        if self.s.cookie:
            h = {
                "Cookie": self.s.cookie,
                "Origin": self.s.server,
                "Referer": f"{self.s.server}/metadata/graphiql/",
            }
            m = re.search(r"XSRF-TOKEN=([^;]+)", self.s.cookie)
            if m:
                h["X-XSRF-TOKEN"] = m.group(1)
            return h
        return {"X-Tableau-Auth": self._get_token()}

    def _get_token(self, *, force: bool = False) -> str:
        if self._token and not force:
            return self._token
        s = self.s
        if not (s.pat_name and s.pat_secret):
            if self._token:
                return self._token
            raise TableauError("No credentials configured for sign-in.")
        body = json.dumps(
            {
                "credentials": {
                    "personalAccessTokenName": s.pat_name,
                    "personalAccessTokenSecret": s.pat_secret,
                    "site": {"contentUrl": s.site_content_url},
                }
            }
        ).encode()
        url = f"{s.server}/api/{self.api_version()}/auth/signin"
        try:
            cred = self._request(url, data=body)["credentials"]
        except urllib.error.HTTPError as e:
            hint = ""
            if e.code == 401:
                hint = (
                    " Check the PAT name/secret and TABLEAU_SITE_CONTENT_URL. "
                    "On SSO tenants PATs may be disabled; use TABLEAU_AUTH_TOKEN or TABLEAU_COOKIE."
                )
            raise TableauError(f"Sign-in failed: {self._http_message(e)}{hint}") from None
        except (urllib.error.URLError, KeyError, ValueError) as e:
            raise TableauError(f"Sign-in failed: {e}") from None
        self._token = cred["token"]
        return self._token

    def signout(self) -> None:
        if self._token and not self.s.cookie and not self.s.auth_token:
            with contextlib.suppress(Exception):  # best effort on shutdown
                self._request(
                    f"{self.s.server}/api/{self.api_version()}/auth/signout",
                    data=b"",
                    headers={"X-Tableau-Auth": self._token},
                )
            self._token = None

    # ---------- endpoint detection ----------
    def _candidates(self) -> list[str]:
        if self.s.metadata_path:
            path = self.s.metadata_path
            return [self.s.server + (path if path.startswith("/") else "/" + path)]
        return [
            f"{self.s.server}/api/metadata/graphql",  # documented standard (Server + Cloud)
            f"{self.s.server}/relationship-service-war/graphql",  # on-prem backend alias
        ]

    def _resolve_endpoint(self) -> str:
        if self._endpoint:
            return self._endpoint
        probe = json.dumps({"query": "{ __typename }"}).encode()
        last_err: urllib.error.HTTPError | urllib.error.URLError | None = None
        for url in self._candidates():
            try:
                d = self._request(url, data=probe, headers=self._auth_headers())
                if isinstance(d, dict) and ("data" in d or "errors" in d):
                    self._endpoint = url
                    log.info("metadata endpoint: %s", url)
                    return url
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 400:  # endpoint is live, just rejected the probe → use it
                    self._endpoint = url
                    return url
                if e.code in (401, 403) and not self.s.cookie and not self.s.auth_token:
                    self._get_token(force=True)  # refresh once, then let the loop retry this url
                    try:
                        self._request(url, data=probe, headers=self._auth_headers())
                        self._endpoint = url
                        return url
                    except urllib.error.HTTPError as e2:
                        last_err = e2
                # 404 / other → try the next candidate
            except urllib.error.URLError as e:
                last_err = e
        raise TableauError(
            "Could not reach the Metadata API at "
            + " or ".join(self._candidates())
            + (f" ({self._http_message(last_err)})" if isinstance(last_err, urllib.error.HTTPError) else "")
            + ". On Tableau Server the Metadata API must be enabled "
            "(`tsm maintenance metadata-services enable`); on Cloud it is always on."
        )

    # ---------- GraphQL ----------
    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            url = self._resolve_endpoint()
        payload = json.dumps({"query": query, "variables": variables or {}}).encode()
        try:
            return self._request(url, data=payload, headers=self._auth_headers())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) and not self.s.cookie and not self.s.auth_token:
                self._get_token(force=True)
                try:
                    return self._request(url, data=payload, headers=self._auth_headers())
                except urllib.error.HTTPError as e2:
                    raise TableauError(f"Metadata API error: {self._http_message(e2)}") from None
            raise TableauError(f"Metadata API error: {self._http_message(e)}") from None
        except urllib.error.URLError as e:
            raise TableauError(f"Metadata API unreachable: {e}") from None

    # ---------- context ----------
    def server_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "server": self.s.server,
            "site_content_url": self.s.site_content_url or "(default)",
            "auth": "cookie" if self.s.cookie else ("token" if self.s.auth_token else "pat"),
        }
        try:
            si = self._request(f"{self.s.server}/api/serverinfo").get("serverInfo") or {}
            pv = si.get("productVersion")
            info["product_version"] = pv.get("value") if isinstance(pv, dict) else pv
            info["rest_api_version"] = si.get("restApiVersion")
        except Exception:  # noqa: BLE001
            pass
        with self._lock:
            info["metadata_endpoint"] = self._resolve_endpoint()
        # Heuristic Catalog (Data Management) availability: can we read external assets?
        probe = self.graphql("{ databaseTablesConnection(first: 1) { totalCount } }")
        if probe.get("errors"):
            info["catalog_note"] = (
                "external-asset queries returned an error (Data Management add-on may be absent)"
            )
            info["catalog_available"] = False
        else:
            n = (((probe.get("data") or {}).get("databaseTablesConnection")) or {}).get("totalCount")
            info["database_tables_visible"] = n
            info["catalog_available"] = bool(n)
        return info
