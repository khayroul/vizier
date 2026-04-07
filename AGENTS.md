# Vizier Agent System

Vizier is a governed, self-improving AI production engine built on the Hermes Agent runtime.

## Architecture

- **Runtime:** Hermes Agent v0.7.0 — provides tool execution, conversation management, and agent orchestration
- **Governance:** Pydantic contracts define every artifact spec, policy decision, and quality gate
- **Storage:** PostgreSQL 16 + pgvector for structured data; MinIO for binary assets
- **Observability:** Langfuse for tracing; local spans for detailed step tracking
- **Models:** GPT-5.4-mini for all text tasks (Month 1-2); FLUX/Kontext/Nano Banana for images

## Key Contracts

- `contracts/artifact_spec.py` — Defines what to produce (type, style, constraints)
- `contracts/policy.py` — Centralised policy decisions (phase-gated, auditable)
- `contracts/publishing.py` — NarrativeScaffold, CharacterBible, StoryBible, StyleLock
- `contracts/routing.py` — Model and workflow routing decisions

## Tools

Custom Hermes tools in `tools/` handle specific production tasks: poster generation, image synthesis, research, publishing, and more. Each tool is registered with Hermes and governed by quality middleware.

## Workflows

Workflow definitions in `manifests/workflows/` describe multi-step production pipelines as YAML. The generic executor processes these — no per-workflow code needed.

## Quality

Every artifact passes through quality gates (`middleware/`) with tripwire checks, parallel guardrails, and exemplar-anchored scoring. Critique-then-revise, never score-only retry.
