# Workstation GUI optimization progress

**Branch:** `work/gui-polish`  
**Starting baseline:** `072c418cd5371a25a29ad6282356e22b5ecc4d22`  
**Scope:** Workstation presentation, observability, accessibility, browser contracts.

## Milestone status

| Stage | Status | Result |
| --- | --- | --- |
| G1 — Audit current UX + baseline smoke | Complete | Canonical shell, security contracts, presentation metadata, docs and browser fixture audited; deterministic Playwright baseline passed. |
| G2 — Establish design hierarchy/tokens | Complete | Added a small additive token layer for surfaces, borders, focus, status and radii without a framework migration. |
| G3 — Chat/composer/sidebar polish | Complete | Improved long-answer measure, privacy visibility and navigation state without changing backend semantics. |
| G4 — Activity/status observability | Complete | Added metadata-driven context utilization and clearer bounded activity labels. |
| G5 — Research/source inspector polish | Complete | Surface existing authority and transport provenance progressively on source cards. |
| G6 — Develop-mode workflow polish | Complete | Existing PLAN → IMPLEMENT → VERIFY rail retained and visually clarified; no development policy changes. |
| G7 — Artifact/preview refinement | Complete | Existing sandboxed HTML/SVG/local-diagram path retained; presentation consistency verified. |
| G8 — Responsive/accessibility pass | Complete | Added focus-visible treatment, reduced-motion handling, touch-target refinements and semantic current-navigation state. |
| G9 — Browser performance/regression pass | Complete | No new runtime dependency/framework; browser smoke extended for observability contracts and rerun. |
| G10 — Final smoke + integration handoff | Complete | Final targeted tests, deterministic browser smoke, responsive overflow checks and branch comparison passed; ready for coordinator review. |

## UX audit findings

The canonical shell already had the correct architecture: one coherent chat surface, a persistent inspector, explicit network policy, local-only assets, bounded research activity, development phases and safe artifact previews. The highest-value changes were therefore state clarity and progressive disclosure rather than structural redesign.

Primary friction found:

- privacy state was configured but not visible when the options panel was closed;
- context capacity metadata existed in the presentation contract but had no compact top-level representation;
- source authority and fetched-page versus search-snippet transport were available but hidden in advanced provenance;
- current navigation state relied mainly on visual styling;
- focus and reduced-motion behavior needed explicit polish;
- long assistant answers could use a tighter reading measure without narrowing code/artifact surfaces.

## Decisions

### DECISION — Keep the canonical lightweight shell

**RATIONALE:** Existing HTML/CSS/JavaScript already satisfies the product architecture and deterministic security smoke.  
**ALTERNATIVES:** Framework migration or parallel frontend.  
**ACCESSIBILITY IMPACT:** Neutral-to-positive; native controls remain.  
**SECURITY IMPACT:** No new execution surface or remote dependency.  
**PERFORMANCE IMPACT:** Avoids framework/runtime cost.  
**COMPATIBILITY IMPACT:** Preserves current Workstation API contracts.

### DECISION — Use canonical safe-input context utilization

**RATIONALE:** User-facing pressure must reflect the Context Engine's admissible input budget, not prompt tokens divided by the physical model window. The GUI therefore prefers `context_utilization_percent`, consumes `input_budget_tokens`, and supports `actual_provider_prompt_tokens`; `physical_context_utilization_percent` is secondary diagnostic context only. When the canonical percentage is absent, the only fallback calculation uses prompt tokens divided by the canonical safe input budget.  
**ALTERNATIVES:** Physical-window utilization, hard-coded model limits, or permanently visible empty meters.  
**ACCESSIBILITY IMPACT:** Text percentage plus detailed tooltip; not color-only.  
**SECURITY IMPACT:** Uses emitted metadata only; no prompts or private reasoning exposed.  
**PERFORMANCE IMPACT:** Constant-time DOM update.  
**COMPATIBILITY IMPACT:** Gracefully hidden when safe-input budget metadata is unavailable; older physical-window-only metadata is not misrepresented as safe capacity.

### DECISION — Surface evidence authority and transport progressively

**RATIONALE:** Users should distinguish a primary source from the transport used to obtain it, especially fetched pages versus search snippets.  
**ALTERNATIVES:** Put all provenance on every card or infer confidence in the browser.  
**ACCESSIBILITY IMPACT:** Text labels rather than color-only semantics.  
**SECURITY IMPACT:** No direct remote fetch or image loading introduced.  
**PERFORMANCE IMPACT:** At most three small tags per source card.  
**COMPATIBILITY IMPACT:** Optional fields; cards remain valid without them.

### DECISION — Preserve artifact sandbox and CSP unchanged

**RATIONALE:** Presentation polish does not justify expanding generated-content privileges.  
**ALTERNATIVES:** Script-enabled preview or remote resources.  
**ACCESSIBILITY IMPACT:** Neutral.  
**SECURITY IMPACT:** Preserves deny-by-default inner CSP and empty iframe sandbox.  
**PERFORMANCE IMPACT:** Neutral.  
**COMPATIBILITY IMPACT:** Existing artifact behavior retained.

## Governor follow-up

An independent integration-governor review found that the first context meter revision incorrectly divided prompt tokens by the physical context window. That defect is corrected on this branch: an 8K physical window with a 6,144-token safe input budget and `context_utilization_percent=100` now renders `Input 100%`, not `Context 75%`. The browser contract also verifies `actual_provider_prompt_tokens` handling and refuses to show a safe-capacity chip from physical-window-only metadata.

This resolves the identified GUI semantic defect, but does **not** authorize merge by itself. Final integration still requires Runtime/Context/Research/Development stabilization, updating this branch against resulting `main`, full PR CI, integrated Playwright smoke, and the target-machine human visual review.

## Integration notes

The GUI branch intentionally avoids broad edits to `src/reverend/workstation/service.py`, runtime scheduling, research ranking, Context Compiler internals and the development engine. Future runtime/context/research branches can expose richer normalized fields through the existing presentation metadata contract; the GUI hides unsupported observability rather than inventing it.
