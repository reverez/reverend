"""Bounded Knowledge Fabric ranking and lazy semantic cache.

M10 deliberately reranks only bounded candidates. It never scans or embeds a
reference corpus wholesale.
"""
from __future__ import annotations

import hashlib
import math
import sqlite3
import struct
from pathlib import Path

from reverend.runtime import ModelRole

MAX_FABRIC_CANDIDATES = 12
MAX_EMBED_CHARS = 3000
DEFAULT_CACHE_ENTRIES = 50_000


class KnowledgeFabricError(RuntimeError):
    code = "knowledge_fabric_failed"


def _candidate_text(row: dict) -> str:
    parts = [
        str(row.get("source_title", "")).strip(),
        str(row.get("section", "")).strip(),
        str(row.get("content", "")).strip()[:MAX_EMBED_CHARS],
    ]
    return "\n".join(part for part in parts if part)


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pack(vector) -> bytes:
    values = tuple(float(value) for value in vector)
    if (
        not values
        or len(values) > 65_536
        or not all(math.isfinite(value) for value in values)
    ):
        raise KnowledgeFabricError("Embedding vector is invalid")
    return struct.pack(f"<{len(values)}f", *values)


def _unpack(blob: bytes, dimensions: int) -> tuple[float, ...] | None:
    if dimensions <= 0 or len(blob) != dimensions * 4:
        return None
    values = struct.unpack(f"<{dimensions}f", blob)
    return values if all(math.isfinite(value) for value in values) else None


def _number(value, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _cosine(left, right) -> float:
    if len(left) != len(right) or not left:
        raise KnowledgeFabricError("Embedding dimensions do not match")
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


class LazyEmbeddingCache:
    """Small local cache for candidate embeddings, never raw source text."""

    def __init__(self, path: Path, *, max_entries: int = DEFAULT_CACHE_ENTRIES):
        if max_entries < 1:
            raise ValueError("Embedding cache must allow at least one entry")
        self.path = Path(path)
        self.max_entries = max_entries
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=5) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=5000")
            db.execute(
                """CREATE TABLE IF NOT EXISTS passage_embeddings(
                    cache_key TEXT PRIMARY KEY,
                    model_key TEXT NOT NULL,
                    passage_hash TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    vector BLOB NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_passage_embeddings_model "
                "ON passage_embeddings(model_key)"
            )

    @staticmethod
    def key(model_key: str, passage_hash: str) -> str:
        return hashlib.sha256(
            (model_key + "\0" + passage_hash).encode("utf-8")
        ).hexdigest()

    def get(self, model_key: str, passage_hash: str):
        key = self.key(model_key, passage_hash)
        with sqlite3.connect(self.path, timeout=5) as db:
            db.execute("PRAGMA busy_timeout=5000")
            row = db.execute(
                "SELECT dimensions, vector FROM passage_embeddings WHERE cache_key=?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return _unpack(row[1], int(row[0]))

    def put(self, model_key: str, passage_hash: str, vector) -> None:
        blob = _pack(vector)
        dimensions = len(blob) // 4
        key = self.key(model_key, passage_hash)
        with sqlite3.connect(self.path, timeout=5) as db:
            db.execute("PRAGMA busy_timeout=5000")
            db.execute(
                """INSERT OR REPLACE INTO passage_embeddings(
                    cache_key,model_key,passage_hash,dimensions,vector
                ) VALUES(?,?,?,?,?)""",
                (key, model_key, passage_hash, dimensions, blob),
            )
            count = int(
                db.execute("SELECT COUNT(*) FROM passage_embeddings").fetchone()[0]
            )
            excess = count - self.max_entries
            if excess > 0:
                db.execute(
                    """DELETE FROM passage_embeddings WHERE cache_key IN (
                        SELECT cache_key FROM passage_embeddings
                        ORDER BY rowid ASC LIMIT ?
                    )""",
                    (excess,),
                )

    def count(self) -> int:
        with sqlite3.connect(self.path, timeout=5) as db:
            return int(
                db.execute("SELECT COUNT(*) FROM passage_embeddings").fetchone()[0]
            )


class KnowledgeFabric:
    """Rank bounded candidates with deterministic signals plus lazy embeddings."""

    def __init__(
        self,
        cache_path: Path,
        *,
        max_candidates: int = MAX_FABRIC_CANDIDATES,
    ):
        if not 1 <= max_candidates <= MAX_FABRIC_CANDIDATES:
            raise ValueError("Invalid Knowledge Fabric candidate budget")
        self.max_candidates = max_candidates
        self.cache = LazyEmbeddingCache(cache_path)

    @staticmethod
    def _method_score(row: dict) -> float:
        return {
            "exact_title": 1.0,
            "title_index": 0.8,
            "lexical": 0.5,
        }.get(str(row.get("reference_method", "")), 0.4)

    @staticmethod
    def _model_key(scheduler) -> str:
        try:
            resolved = scheduler.registry.resolve(ModelRole.EMBED)
            return resolved.spec.model + "@" + (resolved.digest or "unknown")
        except Exception:
            try:
                spec = scheduler.registry.spec(ModelRole.EMBED)
                return spec.model + "@unknown"
            except Exception:
                return "embed@unknown"

    @staticmethod
    def _can_embed(
        scheduler,
        reserve_model_calls: int,
    ) -> tuple[bool, str]:
        if scheduler is None:
            return False, "no_scheduler"

        # Wrapper layers expose delegation methods even when the injected base
        # scheduler cannot actually embed. Walk known wrapper seams so tests and
        # reduced runtimes do not spend a failed model-call budget on reranking.
        target = scheduler
        visited = set()
        while id(target) not in visited:
            visited.add(id(target))
            if hasattr(target, "scheduler"):
                target = target.scheduler
                continue
            if hasattr(target, "_scheduler"):
                target = target._scheduler
                continue
            break

        if not hasattr(target, "embed"):
            return False, "embedding_unavailable"

        budget = getattr(scheduler, "budget", None)
        runs = getattr(scheduler, "runs", None)
        if budget is not None and runs is not None:
            remaining = int(budget.max_model_calls) - len(runs)
            if remaining <= reserve_model_calls:
                return False, "model_budget"
        return True, "available"

    def _deterministic(
        self,
        query: str,
        rows: list[dict],
        *,
        status: str,
        limit: int,
    ) -> list[dict]:
        from reverend.intelligence.evidence import relevance_score

        result = []
        for original in rows:
            row = dict(original)
            lexical = relevance_score(query, row)
            method = self._method_score(row)
            row.update(
                fabric_lexical_score=round(lexical, 6),
                fabric_method_score=round(method, 6),
                semantic_score=None,
                fabric_score=round(0.8 * lexical + 0.2 * method, 6),
                fabric_rerank_status=status,
                embedding_cache_hit=None,
            )
            result.append(row)
        result.sort(
            key=lambda row: (
                -_number(row.get("fabric_score")),
                -_number(row.get("relevance")),
                str(row.get("source", "")),
            )
        )
        for rank, row in enumerate(result, 1):
            row["fabric_rank"] = rank
        return result[:limit]

    def rerank(
        self,
        query: str,
        rows,
        *,
        scheduler,
        limit: int,
        reserve_model_calls: int = 1,
    ) -> list[dict]:
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError("Invalid Knowledge Fabric query")
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 0 <= limit <= 50
        ):
            raise ValueError("Invalid Knowledge Fabric result limit")
        if reserve_model_calls < 0:
            raise ValueError("Invalid reserved model-call budget")
        if limit == 0:
            return []

        candidates = [dict(row) for row in rows[: self.max_candidates]]
        if not candidates:
            return []

        can_embed, reason = self._can_embed(scheduler, reserve_model_calls)
        if not can_embed:
            return self._deterministic(
                query,
                candidates,
                status="skipped_" + reason,
                limit=limit,
            )

        model_key = self._model_key(scheduler)
        texts = [_candidate_text(row) for row in candidates]
        hashes = [_text_hash(text) for text in texts]
        vectors = [self.cache.get(model_key, digest) for digest in hashes]
        misses = [i for i, vector in enumerate(vectors) if vector is None]

        try:
            embedded = scheduler.embed(
                [query] + [texts[index] for index in misses]
            )
        except Exception:
            return self._deterministic(
                query,
                candidates,
                status="fallback_embedding_error",
                limit=limit,
            )

        if len(embedded) != 1 + len(misses):
            raise KnowledgeFabricError("Embedding count mismatch during rerank")

        query_vector = tuple(float(value) for value in embedded[0])
        for offset, index in enumerate(misses, 1):
            vector = tuple(float(value) for value in embedded[offset])
            self.cache.put(model_key, hashes[index], vector)
            vectors[index] = vector

        from reverend.intelligence.evidence import relevance_score

        ranked = []
        miss_set = set(misses)
        for index, original in enumerate(candidates):
            row = dict(original)
            lexical = relevance_score(query, row)
            method = self._method_score(row)
            semantic = (_cosine(query_vector, vectors[index]) + 1.0) / 2.0
            row.update(
                fabric_lexical_score=round(lexical, 6),
                fabric_method_score=round(method, 6),
                semantic_score=round(semantic, 6),
                fabric_score=round(
                    0.55 * semantic + 0.30 * lexical + 0.15 * method,
                    6,
                ),
                fabric_rerank_status="semantic_embedding",
                embedding_cache_hit=index not in miss_set,
                embedding_model=model_key,
            )
            ranked.append(row)

        ranked.sort(
            key=lambda row: (
                -_number(row.get("fabric_score")),
                -_number(row.get("relevance")),
                str(row.get("source", "")),
            )
        )
        for rank, row in enumerate(ranked, 1):
            row["fabric_rank"] = rank
        return ranked[:limit]
