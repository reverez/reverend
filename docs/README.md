# Reverend legacy/local documentation

This directory contains the documentation for the **existing local Reverend 0.4.0 product line and its historical implementation milestones**.

The new Cloud architecture is intentionally kept separate:

- [Cloud Analysis](../Documentation/Analysis/)
- [Cloud Design](../Documentation/Design/00-design-index.md)
- [Complete Cloud system diagram](../Documentation/Design/system-complete-mermaid-diagram.md)

## Structure

```text
docs/
├── current/
│   ├── architecture/     local 0.4.0 architecture and workstation behavior
│   ├── guides/           operator/setup guides
│   ├── operations/       roadmap, repository and development workflow
│   └── release/          0.4.0 release and final accepted validation
│
└── history/
    ├── milestones/       M6–M18 acceptance/progress records
    ├── optimization/     later optimization workstream records
    ├── vnext-foundation/ original vNext/Wave-1 foundation records
    └── wave2/            Wave-2 specialist/capability records
```

## Current local documentation

### Architecture

- [Knowledge Fabric V2](current/architecture/knowledge-fabric-v2.md)
- [Adaptive intelligence](current/architecture/intelligence.md)
- [Safety and recovery](current/architecture/safety.md)
- [Local workstation](current/architecture/workstation.md)

### Guides

- [Offline reference providers](current/guides/reference-provider.md)
- [Local SearXNG](current/guides/searxng-local.md)

### Operations

- [Development workflow](current/operations/development-workflow.md)
- [Repository consolidation](current/operations/repository-consolidation.md)
- [Roadmap](current/operations/roadmap.md)

### Release

- [Reverend 0.4.0 release notes](current/release/release-0.4.0.md)
- [Final accepted local validation](current/release/final-acceptance.md)

## Historical documentation

Historical files are retained because they record the design and validation lineage that led to the accepted 0.4.0 baseline.

- `history/milestones/` groups M6–M18 by milestone.
- `history/optimization/` contains the runtime, context, research, GUI and development-agent optimization workstreams plus the backend Wave-1 live validation.
- `history/vnext-foundation/` contains the frozen vNext architecture, foundation candidates and full-system alpha programme.
- `history/wave2/` contains the Wave-2 executive, specialist, assurance, GUI and asset design records.

These files are **historical evidence**, not competing current architecture specifications.

## Documentation authority

For the current Cloud programme, use this order:

1. `Documentation/Analysis/A12-cloud-architecture-acceptance.md`
2. `Documentation/Design/`
3. the accepted A0–A11 Analysis records
4. this `docs/current/` local-baseline documentation
5. `docs/history/` for implementation lineage and historical evidence

Two top-level compatibility aliases — `docs/release-0.4.0.md` and `docs/roadmap.md` — are intentionally retained because the existing 0.4.0 release validator and historical external references depend on those paths. New links should use the canonical `docs/current/` locations.

The reorganization in this directory is documentation cleanup; it does not change runtime behavior.
