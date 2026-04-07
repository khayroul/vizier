# Decision: Hermes Agent Fork Assessment

## Status

Pending — deferred to S14 (Hermes fork patch session).

## Context

The architecture (§6, §14) describes a potential fork of Hermes Agent to add
Vizier-specific capabilities (gate2 patch). The fork assessment requires
comparing our needed modifications against the upstream codebase.

## Findings (S0)

- No `vizier-gate2-patch` directory found at `~/vizier-gate2-patch`,
  `~/executor/vizier-gate2-patch`, or `/Users/Executor/vizier-gate2-patch`.
- The patch work has not yet been started or was done in a different location.
- Hermes Agent submodule is pinned to tag v2026.4.3 (see hermes_version.md).

## Next Steps (S14)

1. Analyze which Hermes internals need modification for Vizier governance
2. Determine if changes can be achieved via plugins/middleware without forking
3. If fork is needed: create patch branch, document all modifications
4. Maintain upstream compatibility for future Hermes updates

## Anti-Drift Rule #6

No Hermes-native types may leak into domain contracts. This constraint holds
regardless of whether we fork or use Hermes as-is via middleware adaptation.
