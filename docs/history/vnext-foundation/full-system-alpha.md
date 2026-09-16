# Reverend vNext Full-System Alpha

**Status:** active integration programme  
**Base:** `baseline/vnext-wave2-accepted@b8617b8fed546463ff8e6113cff58507ebf641aa`  
**Branch:** `vnext/full-system-alpha`

## Objective

Complete the remaining Reverend vNext subsystem stack from the accepted Wave-2 baseline while preserving all accepted runtime, security, verification, evidence, privacy, and authority boundaries.

## Programme

The coordinator owns milestone slots `M-VNEXT-07` through `M-VNEXT-22`. Implementation proceeds in dependency order with a green exact-head checkpoint after each accepted milestone.

The fixed milestone sequence is:

| Milestone | Subsystem |
| --- | --- |
| M-VNEXT-07 | Failure Investigator |
| M-VNEXT-08 | Performance Intelligence |
| M-VNEXT-09 | Dependency / Migration Intelligence |
| M-VNEXT-10 | UX / Accessibility Intelligence |
| M-VNEXT-11 | Historian |
| M-VNEXT-12 | Docs / Release Intelligence |
| M-VNEXT-13 | Full Asset Fabric |
| M-VNEXT-14 | Simulation Fabric |
| M-VNEXT-15 | Automation |
| M-VNEXT-16 | Deployment |
| M-VNEXT-17 | External Gateway |
| M-VNEXT-18 | Model Lab |
| M-VNEXT-19 | Quality-Aware Routing |
| M-VNEXT-20 | Controlled Self-Maintenance |
| M-VNEXT-21 | Command Center GUI |
| M-VNEXT-22 | End-to-End Acceptance |

This sequence is dependency ordered. A later milestone must not be pulled forward merely because its implementation appears convenient.

## Non-negotiable invariants

- all model inference remains local unless a later explicit architecture decision changes that contract;
- network use remains governed by typed OFF / ASK / AUTO policy;
- external and retrieved material remains untrusted data;
- deterministic verification outranks model confidence;
- orchestration is bounded and non-recursive;
- workers do not receive arbitrary host shell or filesystem authority;
- software-development changes remain isolated in task worktrees;
- AI-generated changes are never auto-merged;
- the existing Control Plane remains the single authoritative workflow/task/job/artifact state surface;
- no subsystem may introduce a competing execution authority;
- accepted Wave-1 and Wave-2 behavior must remain regression-covered;
- important failures become benchmark/regression cases;
- hardware/model/runtime changes require targeted live validation.

## Milestone discipline

For each milestone:

1. audit the current exact head and relevant accepted contracts;
2. add or update typed interfaces before broad implementation;
3. implement the smallest complete vertical slice;
4. add targeted deterministic tests and benchmark coverage;
5. run targeted tests;
6. run the full portable suite;
7. run live validation when the milestone touches real models, GPU/runtime, network research, GUI, or execution;
8. record acceptance evidence;
9. freeze the known-good checkpoint before proceeding.

## Final alpha gate

The programme is complete only when:

- every milestone has retained acceptance evidence;
- exact-head CI is green;
- whole-system portable validation passes;
- required live model/runtime/research/asset/GUI paths pass;
- authority boundaries remain intact;
- no generated changes have been silently promoted or auto-merged;
- the final accepted SHA is frozen before release/tag work.
