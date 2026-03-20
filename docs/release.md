# Release Validation

Wave 6 standardizes release hardening around one local command:

```bash
searchat validate release
```

That command runs the curated pre-release matrix used to catch contract drift, compatibility regressions, packaging issues, and obvious performance regressions before cutting a release.

## Release Groups

| Group | Scope | Purpose |
| --- | --- | --- |
| `contracts` | UI, API, MCP contract suites | Catch public-surface drift before release |
| `compatibility` | storage, config, readiness, search quality acceptance suites | Catch upgrade and operational regressions |
| `performance smoke` | perf gate suite | Catch obvious latency regressions |
| `packaging` | sdist/wheel build, wheel content audit, `twine check` | Catch broken artifacts and metadata drift |

Run the full matrix:

```bash
uv run searchat validate release
```

Run one or more targeted groups:

```bash
uv run searchat validate release --group contracts
uv run searchat validate release --group compatibility --group packaging
```

## Packaging Policy

The packaging group is the local equivalent of the CI build gate. It validates that a release artifact set:

- builds exactly one wheel and one source distribution
- includes `searchat/py.typed`
- includes `searchat/config/settings.default.toml`
- includes web static assets under `searchat/web/static/`
- ships the required CLI entry points
- passes `twine check` when `twine` is installed

This keeps the local release path aligned with CI instead of maintaining separate packaging logic in multiple places.

## Recommended Release Flow

1. Sync the dev environment.

```bash
uv sync --group dev --extra secure
```

2. Run the full release matrix locally.

```bash
uv run searchat validate release
```

3. If packaging-only changes were made, re-run the packaging group explicitly.

```bash
uv run searchat validate release --group packaging
```

4. If the release includes migration or compatibility-sensitive changes, also run the full test suite.

```bash
uv run pytest -v --tb=short
```

## CI Relationship

CI still runs the full cross-platform test matrix. The release validator is not a replacement for that matrix; it is the local release gate that mirrors the highest-value release checks in a single command.
