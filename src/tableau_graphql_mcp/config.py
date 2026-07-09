"""Environment-driven configuration for any Tableau Server or Tableau Cloud site."""

from __future__ import annotations

import os
from dataclasses import dataclass


def normalize_server(url: str) -> str:
    """Return a clean ``https://host`` base with no trailing slash or path."""
    url = (url or "").strip().rstrip("/")
    if not url:
        return url
    if url.startswith(("http://", "https://")):
        # keep scheme + host[:port] only
        scheme, rest = url.split("://", 1)
        host = rest.split("/", 1)[0]
        return f"{scheme}://{host}"
    return "https://" + url.split("/", 1)[0]


@dataclass
class Settings:
    """Connection settings, read from environment variables.

    Required: ``TABLEAU_SERVER`` and either a PAT (``TABLEAU_PAT_NAME`` +
    ``TABLEAU_PAT_SECRET``) or an advanced token/cookie fallback.
    """

    server: str
    site_content_url: str = ""
    pat_name: str | None = None
    pat_secret: str | None = None
    auth_token: str | None = None   # advanced: a pre-obtained X-Tableau-Auth token
    cookie: str | None = None       # advanced: a browser session cookie (SSO tenants where PATs are disabled)
    api_version: str | None = None  # override REST API version; else auto-detected
    metadata_path: str | None = None  # override the GraphQL path; else auto-detected
    timeout: float = 60.0

    @classmethod
    def from_env(cls, env: dict | None = None) -> Settings:
        env = os.environ if env is None else env
        server = env.get("TABLEAU_SERVER", "").strip()
        if not server:
            raise RuntimeError(
                "TABLEAU_SERVER is required, e.g. "
                "https://tableau.company.com (Server) or "
                "https://10ax.online.tableau.com (Cloud)."
            )
        try:
            timeout = float(env.get("TABLEAU_TIMEOUT", "60"))
        except ValueError:
            timeout = 60.0
        s = cls(
            server=normalize_server(server),
            site_content_url=env.get("TABLEAU_SITE_CONTENT_URL", "").strip(),
            pat_name=(env.get("TABLEAU_PAT_NAME") or None),
            pat_secret=(env.get("TABLEAU_PAT_SECRET") or None),
            auth_token=(env.get("TABLEAU_AUTH_TOKEN") or None),
            cookie=(env.get("TABLEAU_COOKIE") or None),
            api_version=(env.get("TABLEAU_API_VERSION") or None),
            metadata_path=(env.get("TABLEAU_METADATA_PATH") or None),
            timeout=timeout,
        )
        s.validate()
        return s

    def validate(self) -> None:
        if self.cookie or self.auth_token:
            return
        if not (self.pat_name and self.pat_secret):
            raise RuntimeError(
                "No credentials. Set TABLEAU_PAT_NAME + TABLEAU_PAT_SECRET "
                "(a Personal Access Token; the secret is the whole string, do not split it), "
                "or, for SSO tenants where PATs are disabled, TABLEAU_AUTH_TOKEN "
                "or TABLEAU_COOKIE."
            )
