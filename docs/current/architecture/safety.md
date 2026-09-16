# Safety and recovery

Source notes, textbooks and PDFs are read-only. The platform writes runtime data
only to its configured external AI data root; explicit human approval is required
for real vault promotion. No source files are deleted by index reconciliation.
No credentials, runtime databases, model data or private generated drafts belong
in Git. No package/server installation, global configuration, push or autonomous
local coding delegation is part of normal ingestion.

SQLite is the registry authority; `state.json` is a derived atomic export.
Both ingest entrypoints complete embeddings before modifying the live vector
index. Pending publications are journaled before Qdrant writes and cleared only
with the successful SQLite document/chunk transaction. A source that reverts or
disappears during an interrupted publication still forces reconciliation.
Retries clean old/intermediate generations. A local writer lock prevents
competing ingestion and maintenance. Stop writers and take a SQLite backup
before migrations. A failed run reports errors rather than declaring success.

Backfill never changes source files or Qdrant and refuses to invent documents
for orphan points. Count equality is checked globally and per document. Preserve
backups outside the repository. FTS is disposable and can be rebuilt from
canonical chunk text. Keep old Qdrant collections during disruptive migrations.

AI-generated frontmatter, generated trust classes and the configured draft
source directory are rejected during ingestion. Retrieval excludes known AI
trust classes and draft paths. Note evidence additionally excludes catalogue
records and metadata scaffolding, and accepts trusted primary/personal sources.
Unlabelled or manually relabelled generated content cannot be detected reliably.
Security trust, authority and review status are distinct concepts; the current
minimal metadata does not claim to solve all source-quality ranking.

The note compiler reloads its template, retrieves evidence per coverage item,
validates model structure, evidence IDs and exact supporting excerpts, and
renders Markdown in code. An excerpt citation does not prove a claim follows
from that excerpt: semantic review remains human work. Missing support produces
explicit gaps. Drafts use unique, exclusive file creation outside the vault,
with a provenance sidecar published first, `active: false`, and unreviewed AI
origin markers. Dry-run creates no files and performs no generation. A filesystem
failure between artifact writes can leave an orphan sidecar; it never overwrites
a previous draft or source note.

Untrusted source text is data, never tool instructions. Retrieval and synthesis
have no shell/write/secret capability inferred from source content. No cloud
fallback or recursive ingestion of generated drafts is configured. Future
source promotion must be explicit and preserve origin/review provenance.

## M5 verification

Clean CMake task worktrees configure into `.reverend-build`, build with at most
 two jobs, and discover/run CTest through the existing bounded command runner.
No registered tests is recorded as an optional skipped check, never as a test
pass. Standalone supported preset fields are projected into controlled argv;
external includes, environment/toolchain overrides, complex conditions and
install/package targets require explicit review. Repository build logic is code:
untrusted repositories remain refused by the command runner. Generated build
files are excluded from coding context and changed-file summaries.

Tests default to temporary runtime data instead of production artifacts/worktrees.
