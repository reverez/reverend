# D17 — Repository Intelligence & Code Context

> **Status:** DESIGN ACCEPTED FOR DEVELOPMENT  
> **Research snapshot:** 2026-09-16  
> **Depends on:** A1, A5, D3, D15  
> **Purpose:** Generalize the accepted Python-oriented local codeintel implementation into persistent, version-aware, multi-language Repository Intelligence for autonomous software engineering.

---

## 1. Design Goal

Reverend should answer repository questions through deterministic structure before asking an LLM to infer the answer from large raw file dumps.

~~~text
Agent
  ↓
RepositoryQuery
  ↓
Repository Intelligence
  ├── exact path/file
  ├── symbol/definition
  ├── references/callers
  ├── imports/dependencies
  ├── diagnostics/types
  ├── test/build relationships
  ├── Git history/diff
  └── semantic fallback
  ↓
versioned RepositoryContext Artifact
~~~

---

## 2. Existing Capability to Preserve

The current src/reverend/codeintel subsystem already provides:

- repository scanning;
- changed-file/recent-commit context;
- Python AST symbols/imports/calls;
- Python dependency graph;
- lexical + structural retrieval;
- bounded code context compilation.

These are accepted foundations.

Cloud modernization does not discard them.

Instead:

~~~text
Python-specific local codeintel
→ adapter inside Repository Intelligence Service
~~~

---

## 3. RepositorySnapshot

Every result identifies the exact code state it describes.

~~~text
RepositorySnapshot
├── project_id
├── run_id?
├── workspace_id?
├── canonical repository identity
├── base commit
├── HEAD commit/ref
├── staged/index digest
├── uncommitted diff digest
├── untracked manifest digest
├── snapshot_id
└── created_at
~~~

For clean committed state, commit SHA may be sufficient.

For active worktrees, the snapshot includes hashes of the workspace delta.

A result from snapshot X cannot silently describe snapshot Y.

---

## 4. Index Layers

### Layer 1 — filesystem / Git facts

~~~text
paths
sizes/types
languages
Git status
commits
diffs
renames
branches
worktree identity
~~~

### Layer 2 — syntax structure

~~~text
symbols
definitions
imports/includes
classes
functions/methods
calls where statically extractable
syntax errors
source ranges
~~~

Current Python AST remains an adapter.

Tree-sitter becomes the general structural baseline for supported non-Python languages.

### Layer 3 — language-semantic services

~~~text
definitions
references
implementations
hover/type
diagnostics
workspace symbols
rename preview
call hierarchy where supported
~~~

Potential adapters:

~~~text
Python      Pyright
C/C++/CUDA  clangd
TypeScript  TypeScript language service
Rust        rust-analyzer
~~~

These are implementation candidates, not permanent semantic dependencies.

### Layer 4 — project graph

~~~text
module/package graph
build targets
dependency graph
interfaces
test → source relationships
config/deployment relationships
generated-code relationships
~~~

### Layer 5 — semantic code retrieval

Embeddings/reranking may identify conceptual candidates, but cannot outrank exact symbol/path/graph results merely because similarity is high.

---

## 5. Tree-sitter Role

Tree-sitter is the preferred language-neutral syntax index because it supports incremental parsing and robust concrete syntax trees.

Use cases:

- structural symbols;
- import/include extraction;
- function/class ranges;
- syntax-aware chunk boundaries;
- change-local reindexing;
- languages without richer semantic servers.

Tree-sitter is not a type checker and does not replace compiler/LSP semantics.

---

## 6. LSP / Type-Service Safety

Language servers are execution capabilities, not trusted parsers by assumption.

Rules:

- use pinned known server binaries/packages;
- run under repository analysis sandbox/worker;
- no Secret Broker/DB credentials;
- deny arbitrary workspace commands not required by the adapter;
- network off by default;
- plugin/extension auto-install disabled;
- output is derived intelligence, not authority;
- time/memory/process limits apply.

A repository cannot cause Reverend to download/execute an arbitrary recommended language server.

---

## 7. Repository Index Persistence

Authoritative source remains Git/workspace/Artifacts.

Derived storage:

~~~text
PostgreSQL
  RepositorySnapshot metadata
  index build state
  adapter/tool versions

Blob/derived store
  optional serialized graphs

Qdrant
  semantic vectors

worker/cache
  Tree-sitter parse cache
  LSP state
~~~

Complete index loss is recoverable by reindexing the snapshot.

---

## 8. Incremental Update

On mutation:

~~~text
successful edit/patch
↓
new workspace snapshot identity
↓
invalidate affected files
↓
incremental syntax reparse
↓
update symbol/import/dependency records
↓
refresh semantic vectors only for changed chunks
↓
notify LSP of changed documents
~~~

Commit/checkout/worktree replacement may trigger broader invalidation.

Never reuse an index merely because the filesystem path is unchanged.

---

## 9. Query Contract

RepositoryQuery kinds:

~~~text
REPO_MAP
PATH_LOOKUP
SYMBOL_LOOKUP
DEFINITION
REFERENCES
IMPLEMENTATIONS
CALLERS
IMPORTS
DEPENDENCIES
DIAGNOSTICS
TYPE_INFO
AFFECTED_TESTS
RECENT_CHANGES
DIFF_CONTEXT
TEXT_SEARCH
SEMANTIC_SEARCH
FILE_SLICE
~~~

Every result includes:

~~~text
RepositorySnapshot ID
source path/ranges
adapter used
precision/confidence class
staleness state
provenance
~~~

---

## 10. Retrieval Hierarchy

Preferred order:

~~~text
explicit Task/Artifact file refs
↓
exact path
↓
exact symbol/definition/reference
↓
dependency/test graph
↓
lexical/structural search
↓
semantic code retrieval
↓
broader repository summary
~~~

Context Broker need not use semantic retrieval when deterministic information already answers the question.

---

## 11. Code Chunking

Embedding chunks should follow syntax boundaries where possible:

~~~text
class
function/method
module-level definition group
configuration section
documentation section
~~~

Chunk identity binds:

~~~text
snapshot
path
symbol/range
content hash
parser/chunker version
~~~

Avoid arbitrary token splits through functions unless no parser exists.

---

## 12. Repository Map

RepoMap is a compact first-class derived Artifact.

Potential fields:

- top-level directories;
- languages/build systems;
- major modules/packages;
- entrypoints;
- test layout;
- deployment/config files;
- high-centrality interfaces;
- current changed area.

RepoMap provides low-token orientation.

It does not replace source slices for implementation.

---

## 13. Dependency and Interface Graph

Graph edges may include:

~~~text
IMPORTS
CALLS
IMPLEMENTS
EXTENDS
DEPENDS_ON
TESTS
BUILDS
GENERATES
CONFIGURES
DEPLOYS
REFERENCES
~~~

Each edge records derivation source.

Inferred edges remain distinguishable from compiler/LSP relationships.

---

## 14. Test Impact Mapping

Affected-test candidates derive from:

- direct test imports;
- symbol references;
- build target relationships;
- historical change/test evidence;
- explicit Project configuration.

Targeted tests optimize feedback.

Final verification policy may still require broader suites.

A model cannot declare tests unaffected without deterministic policy support.

---

## 15. MutationScope Integration

Before mutation:

~~~text
TeamPlan
→ effective MutationScope
→ workspace
~~~

Repository Intelligence validates:

- actual changed paths;
- interfaces changed;
- cross-scope dependency impact.

After edits:

~~~text
diff
→ scope check
→ reindex
→ diagnostics
→ affected tests
→ verification
~~~

This creates a deterministic conflict surface for parallel Developer Agents.

---

## 16. Multi-Language Rollout

Implementation priority:

1. Python — retain current AST + add Pyright;
2. C/C++/CUDA — Tree-sitter + clangd;
3. TypeScript/JavaScript — Tree-sitter + TypeScript language service;
4. shell/JSON/YAML/TOML/CMake — structural/config adapters;
5. additional languages as Projects require.

Unsupported language falls back to filesystem/lexical capability rather than fabricated semantic precision.

---

## 17. Repository Research vs Execution

Indexing source does not imply executing it.

Build/test/dependency installation belongs to execution workers under separate policy.

A malicious repository must not gain code execution merely by being indexed.

---

## 18. Context Artifacts

Repository queries produce typed bounded outputs such as:

~~~text
RepositoryLocalization
RepositoryMap
SymbolContext
DependencyContext
DiagnosticContext
ChangeImpactReport
~~~

Raw LSP session state is not durable Project truth.

---

## 19. Cache and Staleness

Derived result validity depends on:

- RepositorySnapshot;
- parser/tool version;
- compile/dependency configuration.

Staleness triggers include:

- file hash change;
- checkout/commit change;
- compile database change;
- dependency config change;
- language-server version change where semantics matter.

Context Compiler refreshes stale mandatory facts.

---

## 20. Resource Placement

Small scans may run in the bounded local sandbox.

Heavy indexing/LSP/build-graph analysis uses CPU worker capacity.

GPU is not required for structural intelligence.

Embedding batches may use CPU or an admitted embedding worker based on measured economics.

Do not keep the A100 alive solely for repository indexing.

---

## 21. Observability

Capture:

- snapshot/index version;
- files/symbols/edges;
- parse errors;
- LSP health;
- index duration;
- incrementally changed files;
- semantic vector count;
- query latency by strategy;
- cache hit/miss;
- stale-result rejection;
- downstream context tokens saved.

---

## 22. Benchmarks

Measure:

- target-file localization accuracy;
- definition/reference precision;
- affected-test recall;
- repository question Hit@K/MRR;
- coding Task success;
- context tokens;
- latency/cost.

A richer index remains only if it improves end-to-end engineering outcomes or materially reduces cost/latency.

---

## 23. Technology Evidence

The 2026-09-16 review supports these adapters:

- Tree-sitter is designed for incremental parsing and updating syntax trees after edits;
- Pyright exposes computed/declared/expected types, import resolution and analysis snapshots through its type-service tooling.

These validate the design without making Reverend permanently dependent on either.

---

## 24. Acceptance Tests

Must prove:

- accepted Python codeintel behavior remains available;
- RepositorySnapshot changes after worktree mutation;
- stale symbol result from old snapshot is rejected;
- index loss is rebuildable from Git/workspace;
- exact symbol query outranks semantic similarity;
- language-server process has no Reverend secrets/network by default;
- malicious repo config cannot install/launch arbitrary plugin through indexing;
- MutationScope violation is detected from actual diff;
- changed file triggers incremental index refresh;
- unsupported language degrades explicitly;
- targeted-test mapping never replaces required final verification silently.

---

## 25. Exit Condition

Repository Intelligence is ready when Agents can navigate a changing repository through snapshot-bound deterministic structure and semantic services, request only relevant source slices, and remain correct across edits without treating a vector index or language server as authoritative state.


---

## 26. Recursive Capability Audit — Parser/LSP Supply Chain & Workspace Isolation

### Parser grammar supply chain

Tree-sitter language grammars/parsers are executable/native dependencies in many packaging forms.

Rules:

- grammars/parsers are pinned Reverend dependencies or reviewed worker-image artifacts;
- repository-provided grammar code is never compiled/loaded automatically;
- grammar/parser identity/version is recorded in index provenance;
- parser update creates a new index version and receives security/regression smoke.

### LSP workspace commands

Some language servers expose command execution, build integration or plugin mechanisms.

The Repository Intelligence adapter allowlists specific read/analysis methods.

By default it denies:

- arbitrary executeCommand requests;
- auto-install of SDKs/extensions/plugins;
- repository-defined executable language-server binary paths;
- package-manager hooks triggered solely for indexing.

If richer build-aware analysis needs execution, it becomes a separate CPU worker capability with ToolPolicy/Action semantics.

### Compile database/config trust

Files such as compile_commands.json, tsconfig, pyproject and build scripts are untrusted repository input.

They may inform parsing/search paths, but paths are normalized to the isolated workspace and cannot redirect the analysis process to arbitrary host-secret paths.

### Derived-index Project isolation

Every index/vector point includes RepositorySnapshot and Project scope.

A query must supply the authorized Project/snapshot filter before ranking.

Cross-Project index reuse is limited to explicitly public/common dependency indexes; Project source code is not globally deduplicated for convenience.


---

## 27. Recursive Capability Audit — Language-Service Configuration Sanitization

Repository configuration may contain settings that cause language tooling to load code or escape the workspace.

Adapters must sanitize/deny dangerous analysis configuration, including equivalent mechanisms for:

- compiler/plugin loading flags;
- clang/driver query execution outside an allowlisted pinned toolchain;
- response/config paths escaping the workspace/toolchain root;
- TypeScript language-service plugins;
- repository-selected arbitrary language-server executable paths;
- extension/plugin discovery;
- shell command substitution/hooks;
- arbitrary external include/search paths into Control Plane secret directories.

When richer compile-time behavior genuinely requires executing Project tooling, move that operation into an explicit CPU build/analysis capability under normal sandbox/ToolPolicy rather than quietly granting the LSP broader authority.

The sanitized effective configuration is recorded in Repository Intelligence provenance.

### Reconstructible snapshot requirement

A durable RepositoryContext/Localization Artifact that references uncommitted workspace state may cross a safe boundary only when the corresponding RepositorySnapshot is reconstructible from durable Git/patch/untracked Blob material.

WorkerDurabilityGate prevents destroying the only filesystem copy of a snapshot that retained Artifacts still depend on.
