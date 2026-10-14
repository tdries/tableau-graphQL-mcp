# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | Yes |
| < 0.2 | No. Upgrade: 0.2.0 fixes a credential leak on redirects. |

## Reporting a vulnerability

Report privately through GitHub:
**[Report a vulnerability](https://github.com/tdries/tableau-graphQL-mcp/security/advisories/new)**.
If you cannot use GitHub, email **tim.dries@biztory.be**. Please do not open a public issue.

What to expect:

- Acknowledgement within **3 business days**, and a first assessment within **10 business days**.
- A fix within **30 days** for high or critical issues, and within **90 days** otherwise.
- Coordinated disclosure through a GitHub Security Advisory, with a CVE where warranted.
  Reporters are credited unless they ask not to be.

## What the server guarantees

- **Read-only.** It only sends GraphQL queries to the Tableau Metadata API. `graphql_query`
  rejects `mutation` and `subscription` operations before anything leaves the process, and
  every tool carries the MCP `readOnlyHint` annotation. There is no SQL, file or shell access.
- **Local and stdio-only.** It runs as a child process of your MCP client and opens **no
  inbound network port**.
- **Credentials from the environment only.** The PAT, token or cookie are never tool
  arguments, never logged and never returned in tool output.
- **Credentials go only to your Tableau host.**
  - HTTPS is required. Plain `http://` is refused unless the host is loopback or you set
    `TABLEAU_ALLOW_HTTP=1`.
  - TLS certificates are always verified against the system trust store.
  - HTTP redirects are refused, so a redirect can never carry your session token to another
    host.
- **Least privilege.** Results are limited to what the PAT's Tableau identity may see.
- **No telemetry.** The server contacts nothing except `TABLEAU_SERVER`.

## Data handling

- **Flow.** Tableau Metadata API, then this server, in memory only, then your MCP client.
  Your client sends tool results to the language model provider it uses. Check that this is
  allowed under your organisation's data policies.
- **Personal data.** Lineage results include Tableau content names and, for owners, the
  username, display name and email address. Nothing else about people is requested.
- **Storage.** Nothing is written to disk and nothing is cached between sessions.
- **Logs.** Logs go to stderr. At `TABLEAU_LOG_LEVEL=DEBUG` they show each HTTP method and
  URL, but never headers, request bodies or secrets.

## Threat model

- **Prompt injection through Tableau content.** Names, descriptions, captions and calculated
  field formulas are written by other people on your site and returned to the model as they
  are. Text in them could try to steer the model. This server cannot change anything, but
  other tools in the same client session might. Keep human confirmation on for write-capable
  tools, and treat lineage results as data, not instructions.
- **A hostile or misconfigured Tableau host, proxy or network.** Mitigated by required HTTPS,
  verified certificates and refused redirects.
- **Supply chain.** One runtime dependency, the MCP SDK.
  - `uv.lock` pins every package by hash.
  - GitHub Actions are pinned by commit SHA.
  - Dependabot updates wait 7 days before adopting a new release, except for security fixes.
  - CodeQL, the OpenSSF Scorecard and a fuzzer for the read-only guard run in CI.
- **Out of scope.** Vulnerabilities in Tableau itself, in your MCP client, or in your model
  provider.

## Verifying a release

Releases are built once in GitHub Actions from the tagged commit.

- **PyPI** uploads use Trusted Publishing. PyPI shows their PEP 740 provenance on each file's
  page.
- **GitHub releases** carry the same wheel and sdist, a CycloneDX SBOM
  (`*.cdx.json`) and a Sigstore signature (`*.sigstore.json`) for each file. To verify a
  download, replace both version numbers with the release you downloaded:

```bash
uvx sigstore verify github --cert-identity https://github.com/tdries/tableau-graphQL-mcp/.github/workflows/release.yml@refs/tags/v0.2.0 tableau_graphql_mcp-0.2.0-py3-none-any.whl
```

## Recommendations

- Use a dedicated PAT with the least privilege required, and rotate it. PATs expire after
  15 days of non-use, or after 1 year.
- Pin a version in production, for example `uvx tableau-graphql-mcp==0.2.0`, and review the
  tool list before granting an agent access.
