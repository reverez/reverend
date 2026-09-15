from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
import yaml
from qdrant_client import QdrantClient, models

from . import __version__
from .config import COLLECTION, DATA_ROOT, QDRANT_PATH, close_qdrant, ollama_host, qdrant_client, runtime_value

OLLAMA = ollama_host()
DATA = DATA_ROOT
DB = QDRANT_PATH
STATE = DATA / "ingestion/state.json"
LOGS = DATA / "logs"
DRAFTS = DATA / "drafts"
GENERAL_MODEL = "qwen3.5-4b-64k"
CODE_MODEL = "qwen3-8b-8k"
REASON_MODEL = "deepseek-r1-8b-8k"
EMBED_MODEL = "bge-m3"
def _configured_vault() -> Path:
    explicit = runtime_value(
        "REVEREND_VAULT",
        "vault",
    )
    if explicit:
        return Path(
            os.path.expandvars(
                os.path.expanduser(str(explicit))
            )
        )

    profile = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "corpora.yaml"
    )
    try:
        data = yaml.safe_load(
            profile.read_text(encoding="utf-8")
        ) or {}
        root = (
            data.get("corpora", {})
            .get("obsidian", {})
            .get("root")
        )
        if root:
            return Path(
                os.path.expandvars(
                    os.path.expanduser(str(root))
                )
            )
    except (OSError, ValueError, TypeError):
        pass

    return (
        Path.home()
        / "Documents"
        / "Notes"
    )


VAULT = _configured_vault()
TEMPLATE = Path(
    runtime_value(
        "REVEREND_TEMPLATE",
        "template",
        str(
            VAULT
            / "03 Systems + Meta"
            / "Master Note Template v20.md"
        ),
    )
)


def api(path: str, payload: dict | None = None, timeout: int = 600) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(OLLAMA + path, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def log_event(task: str, model: str, success: bool, started: float, **details) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "task_type": task, "model": model,
              "success": success, "elapsed_seconds": round(time.monotonic() - started, 3), **details}
    with (LOGS / "tasks.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def embed(texts: list[str]) -> list[list[float]]:
    return api("/api/embed", {"model": EMBED_MODEL, "input": texts})["embeddings"]


def client() -> QdrantClient:
    result = qdrant_client()
    if not result.collection_exists(COLLECTION):
        result.create_collection(COLLECTION, vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE))
        for field in ("source", "source_type", "trust_class", "corpus"):
            result.create_payload_index(COLLECTION, field, models.PayloadSchemaType.KEYWORD)
    return result


def load_state() -> dict:
    if not STATE.exists():
        return {"sources": {}}
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=STATE.parent,
                                         prefix='.state-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, STATE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_chunks(path: Path) -> list[tuple[str, str, int | None]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        document = pymupdf.open(path)
        return [(f"Page {page.number + 1}", page.get_text("text").strip(), page.number + 1)
                for page in document if page.get_text("text").strip()]
    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix != ".md":
        return [(path.stem, text.strip(), None)] if text.strip() else []
    pieces, heading, buffer = [], path.stem, []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match and buffer:
            pieces.append((heading, "\n".join(buffer).strip(), None))
            buffer = []
        if match:
            heading = match.group(2).strip()
        buffer.append(line)
    if buffer:
        pieces.append((heading, "\n".join(buffer).strip(), None))
    output = []
    for section, content, page in pieces:
        if len(content) <= 2400:
            output.append((section, content, page))
        else:
            for start in range(0, len(content), 2200):
                output.append((section, content[start:start + 2400], page))
    return [item for item in output if item[1]]


def source_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".txt", ".pdf"}
                  and ".obsidian" not in path.parts and not path.name.startswith(".~"))


def ingest(root: Path, trust: str, corpus: str) -> dict:
    from .sync import ingest_path
    return ingest_path(root, trust, corpus)


def search(query: str, limit: int = 5, trust: str | None = None,
           corpus: str | None = None, mode: str = 'hybrid') -> list[dict]:
    from .retrieve import retrieve_dense, retrieve_lexical, retrieve_hybrid
    methods = {'dense':retrieve_dense, 'lexical':retrieve_lexical, 'hybrid':retrieve_hybrid}
    if mode not in methods:
        raise ValueError(f'Unknown retrieval mode: {mode}')
    return methods[mode](query, limit, trust=trust, corpus=corpus)


def command_chat(
    text: str,
    mode: str,
    *,
    workstation_factory=None,
) -> int:
    """Run legacy Ask/Reason CLI surfaces through the canonical Workstation."""

    if mode not in {"ask", "reason"}:
        raise ValueError("CLI chat mode must be ask or reason")

    if workstation_factory is None:
        from .workstation.service import Workstation
        workstation_factory = Workstation

    started = time.monotonic()
    app = workstation_factory(DATA_ROOT)
    try:
        submitted = app.chat(
            text,
            mode=mode,
            network_policy="OFF",
            privacy_mode="ephemeral",
        )
        job_id = submitted["job_id"]

        while True:
            job = app.store.job(job_id)
            if job["status"] not in {
                "queued",
                "running",
                "stopping",
            }:
                break
            time.sleep(.05)

        details = dict(job.get("details") or {})
        success = (
            job["status"] == "complete"
            and bool(job.get("response"))
        )
        model = str(
            details.get("model")
            or details.get("role")
            or "workstation"
        )
        log_event(
            mode,
            model,
            success,
            started,
            tools_invoked=[],
            files_changed=[],
        )

        if success:
            print(job["response"])
            return 0

        error_code = details.get("error_code")
        error = (
            details.get("error")
            or "Canonical Workstation inference failed."
        )
        if error_code:
            print(
                f"{error_code}: {error}",
                file=sys.stderr,
            )
        else:
            print(error, file=sys.stderr)
        return 1
    finally:
        app.close()


def command_search(query: str, corpus: str | None = None, *, mode: str = "hybrid",
                   trust: str | None = None, limit: int = 5) -> int:
    rows = search(query, corpus=corpus, mode=mode, trust=trust, limit=limit)
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    return 0 if rows else 1


def command_research(
    query: str,
    *,
    allow_network: bool = False,
    freshness: str | None = None,
    limit: int = 5,
) -> int:
    """Collect bounded local and optional fresh public evidence."""

    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 10
    ):
        raise ValueError("Research limit must be between 1 and 10")

    from reverend.intelligence.contracts import EvidenceClass
    from reverend.intelligence.evidence import select_evidence
    from reverend.intelligence.understanding import freshness_window
    from reverend.research.evidence import public_source_candidate
    from reverend.research.search import bounded_search_query
    from reverend.research.service import PublicResearch
    from reverend.workstation.presentation import source_metadata

    window = freshness or freshness_window(query)
    local_error = None
    try:
        local_candidates = search(query, limit=limit)
    except Exception as exc:
        local_candidates = []
        local_error = {
            "error_code": "local_retrieval_failed",
            "error": f"{type(exc).__name__}: {exc}",
        }

    local_classes = (
        (EvidenceClass.REFERENCE,)
        if window != "stable"
        else (EvidenceClass.PERSONAL, EvidenceClass.REFERENCE)
    )
    local_gate = select_evidence(
        query,
        local_candidates,
        local_classes,
        limit=limit,
        min_relevance=0.50,
    )

    research = PublicResearch(DATA_ROOT / "public-sources.db")
    status = research.search_status()

    result = {
        "query": query,
        "local_evidence": [
            source_metadata(row, index)
            for index, row in enumerate(local_gate.accepted, 1)
        ],
        "local_evidence_gate": local_gate.metadata(),
        "web": {
            "attempted": False,
            "configured": bool(status.get("configured")),
            "freshness": window,
            "status": status,
            "sources": [],
        },
    }

    if local_error is not None:
        result["local_error"] = local_error

    if not allow_network:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if local_error is not None else 0

    result["web"]["attempted"] = True

    if not status.get("configured"):
        result["web"]["error_code"] = status.get(
            "error_code",
            "network_search_unavailable",
        )
        result["web"]["error"] = status.get(
            "error",
            "No web-search provider is configured",
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    discovered = research.discover(
        bounded_search_query(query),
        allow_network=True,
        freshness=window,
        limit=min(3, limit),
    )
    web_candidates = [
        public_source_candidate(
            source,
            index,
            query=query,
        )
        for index, source in enumerate(discovered.get("sources") or [], 1)
    ]
    web_gate = select_evidence(
        query,
        web_candidates,
        (EvidenceClass.FRESH,),
        limit=min(5, limit),
    )
    result["web"].update({
        key: discovered.get(key)
        for key in (
            "provider",
            "freshness",
            "configuration",
            "search_result_count",
            "search_call_count",
            "search_call_budget",
            "followup_query",
            "followup_facet",
            "page_fetch_attempt_count",
            "page_fetch_attempt_budget",
            "fetched_count",
            "snippet_fallback_count",
            "fetch_failure_count",
            "failures",
            "search_strategy",
            "provider_time_range",
            "authority_search_attempted",
            "authority_domains",
            "authority_search_result_count",
            "authority_search_error",
        )
    })
    result["web"]["evidence_gate"] = web_gate.metadata()
    from reverend.research.quality import annotate_evidence_set
    annotated_web,research_quality=annotate_evidence_set(
        query,
        list(web_gate.accepted),
    )
    result["web"]["research_quality"] = research_quality
    result["web"]["sources"] = [
        source_metadata(row, index)
        for index, row in enumerate(annotated_web, 1)
    ]

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _canonical_note_topic(request: str) -> str:
    from .notes import normalize_topic
    return normalize_topic(request)


def command_note(request: str, dry_run: bool = False) -> int:
    from .notes import compile_note
    report = compile_note(request, dry_run=dry_run, template_path=TEMPLATE,
                          drafts=DRAFTS, vault=VAULT)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def status() -> int:
    from .health import snapshot
    print(json.dumps(snapshot(), indent=2))
    return 0


def doctor(deep: bool = False) -> int:
    from .health import check
    report = check(deep)
    print(json.dumps(report, indent=2))
    return 0 if report['ok'] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="reverend")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("ask", "reason", "search", "research", "note"):
        item = sub.add_parser(name); item.add_argument("text")
        if name == "note": item.add_argument("--dry-run", action="store_true")
        if name == "search":
            item.add_argument('--mode', choices=['dense','lexical','hybrid'], default='hybrid')
            item.add_argument('--corpus')
            item.add_argument('--trust')
            item.add_argument('--limit', type=int, default=5)
        if name == "research":
            item.add_argument("--allow-network", action="store_true")
            item.add_argument(
                "--freshness",
                choices=["stable", "day", "week", "month", "year"],
            )
            item.add_argument("--limit", type=int, default=5)
    code = sub.add_parser(
        "code",
        help="Compatibility alias for the verified dev implement path.",
    )
    code.add_argument("repo")
    code.add_argument("text")

    dev = sub.add_parser(
        "dev",
        help="Local autonomous software development.",
    )

    dev_sub = dev.add_subparsers(
        dest="dev_command",
        required=True,
    )

    dev_implement = dev_sub.add_parser(
        "implement",
        help=(
            "Implement a task in an isolated Git "
            "worktree using local models."
        ),
    )

    dev_implement.add_argument(
        "--project",
        required=True,
        type=Path,
        help="Path to a clean Git repository.",
    )

    dev_implement.add_argument(
        "--request",
        required=True,
        help="Natural-language development request.",
    )

    dev_implement.add_argument(
        "--acceptance",
        default=None,
        help="Optional explicit acceptance criteria.",
    )

    dev_implement.add_argument(
        "--max-repairs",
        type=int,
        choices=range(0, 11),
        default=2,
        metavar="N",
        help="Maximum bounded repair attempts (0-10).",
    )

    dev_implement.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON output.",
    )
    ingest_parser = sub.add_parser("ingest"); ingest_parser.add_argument("path"); ingest_parser.add_argument("--trust", default="TRUSTED_PERSONAL"); ingest_parser.add_argument("--corpus", default="local")
    sync_parser = sub.add_parser("sync")
    sync_mode = sync_parser.add_mutually_exclusive_group(
        required=True
    )
    sync_mode.add_argument(
        "--dry-run",
        action="store_true",
    )
    sync_mode.add_argument(
        "--record-baseline",
        action="store_true",
    )
    sync_mode.add_argument(
        "--apply",
        action="store_true",
    )
    sync_parser.add_argument(
        "--config",
        type=Path,
        default=None,
    )

    migrate_qdrant = sub.add_parser("migrate-qdrant")
    migrate_qdrant.add_argument(
        "--target-url",
        default="http://127.0.0.1:6333",
    )
    migrate_qdrant.add_argument(
        "--target-collection",
        default="local_knowledge_v3",
    )
    migrate_qdrant.add_argument(
        "--source-collection",
        default=COLLECTION,
    )
    migrate_qdrant.add_argument(
        "--batch-size",
        type=int,
        default=256,
    )
    migrate_qdrant.add_argument(
        "--state-path",
    )
    migrate_qdrant.add_argument(
        "--reset-state",
        action="store_true",
    )
    sub.add_parser("backfill-chunks")
    sub.add_parser("rebuild-fts")
    sub.add_parser("status")
    sub.add_parser("doctor").add_argument("--deep", action="store_true")
    gui_parser = sub.add_parser("gui")
    gui_parser.add_argument("--port", type=int, default=8765)
    public_fetch = sub.add_parser('web-fetch');public_fetch.add_argument('url');public_fetch.add_argument('--allow-network',action='store_true')
    code_index = sub.add_parser('code-index');code_index.add_argument('repo');code_index.add_argument('--path',action='append',dest='paths')
    code_search = sub.add_parser('code-search');code_search.add_argument('repo');code_search.add_argument('query')
    memory_parser = sub.add_parser('memory', help='Typed engineering evidence')
    memory_commands = memory_parser.add_subparsers(dest='memory_command',required=True)
    memory_search = memory_commands.add_parser('search')
    memory_search.add_argument('project_id'); memory_search.add_argument('query',nargs='?',default='')
    memory_add = memory_commands.add_parser('add')
    for name in ('kind','project_id','content','source','evidence'):memory_add.add_argument(name)
    memory_add.add_argument('--commit',dest='related_commit');memory_add.add_argument('--expires-at')
    memory_archive = memory_commands.add_parser('archive');memory_archive.add_argument('identity')
    benchmark_parser = sub.add_parser(
        "benchmark",
        help="ReverendBench evaluation tools.",
    )
    benchmark_commands = benchmark_parser.add_subparsers(
        dest="benchmark_command",
        required=True,
    )
    benchmark_commands.add_parser(
        "list",
        help="List registered ReverendBench cases.",
    )
    benchmark_commands.add_parser('routing',help='Run deterministic routing acceptance without inference')
    benchmark_run = benchmark_commands.add_parser(
        "run",
        help="Run registered ReverendBench cases.",
    )
    benchmark_run.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="Run only this case ID. May be repeated.",
    )

    args = parser.parse_args(argv)

    if args.command == "benchmark":
        from reverend.benchmarks.catalog import builtin_cases
        from reverend.benchmarks.command import (
            command_benchmark_list,
            command_benchmark_run,
        )

        cases = builtin_cases()

        if args.benchmark_command == "list":
            return command_benchmark_list(cases)

        if args.benchmark_command == 'routing':
            from reverend.benchmarks.routing import run_routing
            run,path=run_routing(DATA_ROOT)
            print(json.dumps({**run.to_dict(),'report_path':str(path)},indent=2))
            return 0 if run.summary.passed==run.summary.total else 1

        if args.benchmark_command == "run":
            return command_benchmark_run(
                cases,
                data_root=DATA_ROOT,
                case_ids=args.case_ids,
            )

        parser.error(
            f"Unknown benchmark command: {args.benchmark_command}"
        )

    if args.command=='web-fetch':
        from reverend.research.service import PublicResearch
        print(json.dumps(PublicResearch(DATA_ROOT/'public-sources.db').fetch(args.url,allow_network=args.allow_network),indent=2));return 0

    if args.command in {'code-index','code-search'}:
        from reverend.codeintel.semantic import build_index,augment
        from reverend.development.coder import create_local_scheduler
        from dataclasses import asdict
        scheduler=create_local_scheduler()
        if args.command=='code-index':result=build_index(args.repo,scheduler,paths=args.paths)
        else:
            search,metadata=augment(args.repo,args.query,scheduler)
            result={**asdict(search),**metadata}
        print(json.dumps(result,indent=2));return 0

    if args.command == 'memory':
        from reverend.engineering_memory import EngineeringMemory
        memory=EngineeringMemory(DATA_ROOT/'engineering-memory.db')
        if args.memory_command=='search':result=memory.search(args.project_id,args.query)
        elif args.memory_command=='archive':result=memory.archive(args.identity)
        else:result={'id':memory.add(args.kind,args.content,args.project_id,args.source,args.evidence,related_commit=args.related_commit,expires_at=args.expires_at)}
        print(json.dumps(result,indent=2));return 0

    if args.command == "gui":
        from .workstation.server import serve
        serve(args.port)
        return 0

    if args.command == "dev":
        if args.dev_command == "implement":
            from .development.command import (
                command_dev_implement,
            )

            return command_dev_implement(
                args.project,
                args.request,
                acceptance=args.acceptance,
                max_repairs=args.max_repairs,
                json_output=args.json_output,
            )

        parser.error(
            f"Unknown dev command: {args.dev_command}"
        )

    if args.command == "sync":
        from .sync import DEFAULT_CONFIG, command_sync

        return command_sync(
            dry_run=args.dry_run,
            record_baseline=args.record_baseline,
            apply=args.apply,
            config_path=args.config or DEFAULT_CONFIG,
        )

    if args.command == "rebuild-fts":
        from .registry import rebuild_fts
        print(json.dumps(rebuild_fts(), indent=2))
        return 0

    if args.command == "migrate-qdrant":
        from .qdrant_migrate import command_migrate_qdrant
        return command_migrate_qdrant(
            target_url=args.target_url,
            target_collection=args.target_collection,
            source_collection=args.source_collection,
            batch_size=args.batch_size,
            state_path=args.state_path,
            reset_state=args.reset_state,
        )

    if args.command == "backfill-chunks":
        from .maintenance import backfill_chunks
        store = client()
        try:
            report = backfill_chunks(store, COLLECTION)
        finally:
            close_qdrant()
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1

    if args.command == "status": return status()
    if args.command == "doctor": return doctor(args.deep)
    if args.command == "ingest":
        from .bulk import ingest_bulk
        report = ingest_bulk(Path(args.path), args.trust, args.corpus)
        print(json.dumps(report, indent=2))
        return 1 if report["errors"] else 0
    if args.command == "search": return command_search(args.text, args.corpus, mode=args.mode, trust=args.trust, limit=args.limit)
    if args.command == "reason": return command_chat(args.text, "reason")
    if args.command == "note": return command_note(args.text, args.dry_run)
    if args.command == "research":
        return command_research(
            args.text,
            allow_network=args.allow_network,
            freshness=args.freshness,
            limit=args.limit,
        )
    if args.command == "ask":
        return command_chat(args.text, "ask")
    if args.command == "code":
        print(
            "NOTICE: 'reverend code' is a compatibility alias; "
            "using the isolated verified development engine.",
            file=sys.stderr,
        )
        from .development.command import command_dev_implement
        return command_dev_implement(
            Path(args.repo),
            args.text,
            max_repairs=2,
            json_output=False,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

