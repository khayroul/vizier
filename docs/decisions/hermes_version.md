# Decision: Hermes Agent Version

## Context

The architecture document references "Hermes Agent v0.7.0" but the NousResearch/hermes-agent
repository uses date-based tags, not semantic versioning. No v0.7.0 tag or branch exists.

## Available Tags (as of 2026-04-07)

- v2026.3.12
- v2026.3.17
- v2026.3.23
- v2026.3.28
- v2026.3.30
- v2026.4.3

## Decision

Using the latest stable tag **v2026.4.3** (2026-04-03) as the submodule reference.
This is the most recent release and closest to our sprint start date.

The commit message for v2026.4.3 confirms: `chore: release v0.7.0 (2026.4.3)`.
So v2026.4.3 **is** the v0.7.0 release referenced in the architecture — the repo
uses date-based tags but this specific release corresponds to the semantic version.

## Impact

None. The submodule is pinned to commit abf1e98f (v2026.4.3 / v0.7.0). Future
sessions (especially S14 — Hermes fork patch) will work with this exact version.
