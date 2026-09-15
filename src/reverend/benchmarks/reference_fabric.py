"""M10 reference retrieval quality and cache benchmark."""
from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def normalize_title(value: str) -> str:
    return " ".join(
        "".join(
            character.casefold()
            if character.isalnum()
            else " "
            for character in str(value).replace("_", " ")
        ).split()
    )


def expected_rank(rows: list[dict], expected_titles: list[str], *, limit: int) -> int | None:
    expected = {normalize_title(value) for value in expected_titles}
    for index, row in enumerate(rows[:limit], 1):
        if normalize_title(row.get("source_title", "")) in expected:
            return index
    return None


def rank_metrics(ranks: list[int | None], *, cutoff: int) -> dict:
    total = len(ranks)
    if not total:
        return {"count": 0, "hit_at_1": 0.0, "hit_at_k": 0.0, "mrr_at_k": 0.0}
    return {
        "count": total,
        "hit_at_1": round(sum(rank == 1 for rank in ranks) / total, 6),
        "hit_at_k": round(
            sum(rank is not None and rank <= cutoff for rank in ranks) / total,
            6,
        ),
        "mrr_at_k": round(
            sum((1.0 / rank) if rank is not None and rank <= cutoff else 0.0 for rank in ranks)
            / total,
            6,
        ),
    }


def latency_metrics(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "median_ms": 0.0, "mean_ms": 0.0, "max_ms": 0.0}
    return {
        "count": len(values),
        "median_ms": round(statistics.median(values) * 1000.0, 3),
        "mean_ms": round(statistics.fmean(values) * 1000.0, 3),
        "max_ms": round(max(values) * 1000.0, 3),
    }


def run_reference_fabric_benchmark(
    provider,
    fabric,
    scheduler,
    cases: list[dict],
    *,
    limit: int = 5,
    candidate_limit: int = 12,
) -> dict:
    if not 1 <= limit <= candidate_limit <= 12:
        raise ValueError("Invalid reference benchmark limits")

    results = []
    baseline_ranks = []
    rerank_ranks = []
    provider_latencies = []
    cold_latencies = []
    warm_latencies = []
    cold_cache_hits = []
    warm_cache_hits = []

    for case in cases:
        query = str(case["query"]).strip()
        expected_titles = [str(value) for value in case["expected_titles"]]
        if not query or not expected_titles:
            raise ValueError("Reference benchmark cases require query and expected_titles")

        started = time.perf_counter()
        candidates = provider.retrieve(
            query,
            mode="hybrid",
            limit=candidate_limit,
        )
        provider_elapsed = time.perf_counter() - started

        baseline = [dict(row) for row in candidates[:limit]]
        baseline_rank = expected_rank(
            baseline,
            expected_titles,
            limit=limit,
        )

        started = time.perf_counter()
        reranked_cold = fabric.rerank(
            query,
            candidates,
            scheduler=scheduler,
            limit=limit,
            reserve_model_calls=0,
        )
        cold_elapsed = time.perf_counter() - started

        started = time.perf_counter()
        reranked_warm = fabric.rerank(
            query,
            candidates,
            scheduler=scheduler,
            limit=limit,
            reserve_model_calls=0,
        )
        warm_elapsed = time.perf_counter() - started

        rerank_rank = expected_rank(
            reranked_cold,
            expected_titles,
            limit=limit,
        )
        cold_hits = sum(
            row.get("embedding_cache_hit") is True
            for row in reranked_cold
        )
        warm_hits = sum(
            row.get("embedding_cache_hit") is True
            for row in reranked_warm
        )

        baseline_ranks.append(baseline_rank)
        rerank_ranks.append(rerank_rank)
        provider_latencies.append(provider_elapsed)
        cold_latencies.append(cold_elapsed)
        warm_latencies.append(warm_elapsed)
        cold_cache_hits.append(cold_hits)
        warm_cache_hits.append(warm_hits)

        results.append({
            "case_id": str(case.get("case_id", query)),
            "query": query,
            "expected_titles": expected_titles,
            "candidate_count": len(candidates),
            "baseline_rank": baseline_rank,
            "reranked_rank": rerank_rank,
            "baseline_titles": [
                row.get("source_title")
                for row in baseline
            ],
            "reranked_titles": [
                row.get("source_title")
                for row in reranked_cold
            ],
            "provider_latency_ms": round(provider_elapsed * 1000.0, 3),
            "cold_rerank_latency_ms": round(cold_elapsed * 1000.0, 3),
            "warm_rerank_latency_ms": round(warm_elapsed * 1000.0, 3),
            "cold_cache_hits": cold_hits,
            "warm_cache_hits": warm_hits,
            "rerank_status": (
                reranked_cold[0].get("fabric_rerank_status")
                if reranked_cold
                else None
            ),
        })

    baseline_metrics = rank_metrics(baseline_ranks, cutoff=limit)
    reranked_metrics = rank_metrics(rerank_ranks, cutoff=limit)
    cache_entries = None
    try:
        cache_entries = int(fabric.cache.count())
    except (AttributeError, TypeError, ValueError):
        pass

    return {
        "schema_version": 1,
        "case_count": len(results),
        "cutoff": limit,
        "candidate_limit": candidate_limit,
        "baseline": baseline_metrics,
        "reranked": reranked_metrics,
        "quality_delta": {
            "hit_at_1": round(
                reranked_metrics["hit_at_1"] - baseline_metrics["hit_at_1"],
                6,
            ),
            "hit_at_k": round(
                reranked_metrics["hit_at_k"] - baseline_metrics["hit_at_k"],
                6,
            ),
            "mrr_at_k": round(
                reranked_metrics["mrr_at_k"] - baseline_metrics["mrr_at_k"],
                6,
            ),
        },
        "latency": {
            "provider": latency_metrics(provider_latencies),
            "cold_rerank": latency_metrics(cold_latencies),
            "warm_rerank": latency_metrics(warm_latencies),
        },
        "cache": {
            "cold_hits": sum(cold_cache_hits),
            "warm_hits": sum(warm_cache_hits),
            "passage_entries": cache_entries,
        },
        "results": results,
    }


def load_cases(path: Path) -> list[dict]:
    payload = json.loads(Path(path).read_text())
    cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(cases, list) or not cases:
        raise ValueError("Reference benchmark case file is empty or invalid")
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path("benchmarks/reference-fabric-queries.json"),
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path("benchmarks/results/vnext/m10/reference-fabric"),
    )
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)

    from reverend.config import DATA_ROOT
    from reverend.development.coder import create_local_scheduler
    from reverend.knowledge import KnowledgeFabric
    from reverend.reference import configured_reference

    provider = configured_reference(DATA_ROOT)
    if provider is None:
        raise SystemExit("No configured REFERENCE provider is available")

    cases = load_cases(args.queries)
    args.report_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="reverend-reference-bench-",
        dir=DATA_ROOT,
    ) as temporary:
        fabric = KnowledgeFabric(Path(temporary) / "cache.db")
        report = run_reference_fabric_benchmark(
            provider,
            fabric,
            create_local_scheduler(),
            cases,
            limit=args.limit,
        )

    report["created_at"] = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.report_root / f"{stamp}.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({**report, "report_path": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
