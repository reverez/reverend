"""Deterministic development-local repository localization.

This module composes Reverend's existing repository scanner, lexical/structural
retrieval and Python dependency graph into a typed development contract. It does
not replace the generic Context Engine and never mutates the repository.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from reverend.codeintel import (
    CodeHit,
    related_python_files,
    scan_python_dependency_graph,
    scan_repository,
    search_code,
    tokenize_query,
)

from .tasks import TaskNotFoundError, get_task


DEFAULT_LOCALIZATION_LIMIT = 8
DEFAULT_SEARCH_LIMIT = 24
DEFAULT_GRAPH_LIMIT = 24
DEFAULT_SEED_LIMIT = 4
DEFAULT_AFFINITY_SOURCE_LIMIT = 12
EXACT_PATH_SCORE_FLOOR = 80.0
EXACT_PATH_BONUS = 24.0

_PATH_MENTION_RE = re.compile(
    r"(?<![\w/-])((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,12})(?![\w/-])"
)


class LocalizationError(RuntimeError):
    """Raised when development localization cannot be produced safely."""


@dataclass(frozen=True)
class LocalizationCandidate:
    path: str
    score: float
    confidence: str
    is_test: bool
    symbols: tuple[str, ...]
    reasons: tuple[str, ...]
    graph_related: bool


@dataclass(frozen=True)
class LocalizationDependency:
    source_path: str
    target_path: str
    relation: str


@dataclass(frozen=True)
class RepositoryMap:
    file_count: int
    test_count: int
    languages: tuple[tuple[str, int], ...]
    build_systems: tuple[str, ...]
    recent_commits: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class LocalizationResult:
    query: str
    candidates: tuple[LocalizationCandidate, ...]
    likely_implementation_paths: tuple[str, ...]
    affected_tests: tuple[str, ...]
    dependencies: tuple[LocalizationDependency, ...]
    repository: RepositoryMap
    excluded_paths: tuple[str, ...]


def _negative_clauses(query: str) -> tuple[str, ...]:
    clauses: list[str] = []
    for raw in re.split(r"(?:\n+|[!?;]+|[.](?=\s|$))", query):
        clause = " ".join(raw.strip().split())
        folded = clause.casefold()
        if not clause:
            continue
        if (
            "do not " in folded
            or "don't " in folded
            or "must not " in folded
            or " untouched" in folded
            or " unchanged" in folded
            or "without changing" in folded
        ):
            clauses.append(clause)
    return tuple(clauses)


def _negative_path_terms(query: str) -> tuple[str, ...]:
    """Extract only high-confidence path hints from explicit negative clauses."""

    terms: list[str] = []
    for clause in _negative_clauses(query):
        folded = clause.casefold()
        tokens = set(tokenize_query(folded))

        if "legacy" in tokens:
            terms.append("legacy")
        if "ui" in tokens:
            terms.append("ui")
        if "docs" in tokens or "documentation" in tokens:
            terms.append("docs")

        match = re.search(
            r"\bwith\s+([a-zA-Z][a-zA-Z0-9_-]*)\s+access\b",
            folded,
        )
        if match:
            terms.append(match.group(1))

        for path in _PATH_MENTION_RE.findall(clause):
            terms.append(path.casefold())

    return tuple(dict.fromkeys(terms))


def _path_matches_negative(path: str, terms: tuple[str, ...]) -> bool:
    folded = path.casefold()
    path_tokens = set(tokenize_query(path))
    parts = {part.casefold() for part in Path(path).parts}
    for term in terms:
        if "/" in term or "." in Path(term).name:
            if folded == term or folded.endswith("/" + term):
                return True
            continue
        if term == "docs" and ("docs" in parts or "documentation" in parts):
            return True
        if term == "ui" and "ui" in parts:
            return True
        if term == "legacy" and "legacy" in parts:
            return True
        if Path(path).stem.casefold() == term:
            return True
        if term in path_tokens and term in {"sqlite", "legacy", "ui", "docs"}:
            return True
    return False



def _mentioned_repository_paths(
    query: str,
    repository_paths: tuple[str, ...],
) -> tuple[str, ...]:
    """Resolve explicit path mentions against the complete repository inventory."""

    lookup = {
        Path(path).as_posix().casefold(): path
        for path in repository_paths
    }
    result: list[str] = []

    for raw in _PATH_MENTION_RE.findall(query):
        normalized = Path(raw).as_posix().casefold()
        actual = lookup.get(normalized)
        if actual is not None and actual not in result:
            result.append(actual)

    return tuple(result)


def _candidate_confidence(score: float, maximum: float, graph_related: bool) -> str:
    if maximum <= 0:
        return "low"
    ratio = score / maximum
    if graph_related and ratio >= 0.35:
        return "high"
    if ratio >= 0.65:
        return "high"
    if ratio >= 0.25:
        return "medium"
    return "low"


def _candidate_from_hit(
    hit: CodeHit,
    *,
    score: float | None = None,
    extra_reasons: tuple[str, ...] = (),
    graph_related: bool = False,
) -> LocalizationCandidate:
    return LocalizationCandidate(
        path=hit.path,
        score=round(hit.score if score is None else score, 3),
        confidence="low",
        is_test=hit.is_test,
        symbols=hit.symbols,
        reasons=tuple(dict.fromkeys((*hit.reasons, *extra_reasons))),
        graph_related=graph_related,
    )


def localize_repository(
    path: str | Path,
    query: str,
    *,
    limit: int = DEFAULT_LOCALIZATION_LIMIT,
    search_limit: int = DEFAULT_SEARCH_LIMIT,
    seed_limit: int = DEFAULT_SEED_LIMIT,
    graph_limit: int = DEFAULT_GRAPH_LIMIT,
) -> LocalizationResult:
    """Return a bounded, typed localization result for one repository request."""

    clean_query = query.strip()
    if not clean_query:
        raise LocalizationError("Localization query cannot be empty.")
    if limit < 1 or limit > 32:
        raise LocalizationError("Localization limit must be between 1 and 32.")

    profile = scan_repository(path, history_limit=8)
    files_by_path = {item.path: item for item in profile.files}
    repository_paths = tuple(files_by_path)

    search = search_code(
        profile.root,
        clean_query,
        limit=max(search_limit, limit),
    )

    # Negative constraints are repository-global. A forbidden path must remain
    # forbidden even when it was not present in the bounded lexical search and
    # only appears later through dependency/test expansion.
    negative_terms = _negative_path_terms(clean_query)
    excluded_set = {
        item.path
        for item in profile.files
        if _path_matches_negative(item.path, negative_terms)
    }
    excluded = tuple(sorted(excluded_set))

    filtered = tuple(
        hit
        for hit in search.hits
        if hit.path not in excluded_set
    )
    scored: dict[str, LocalizationCandidate] = {
        hit.path: _candidate_from_hit(hit)
        for hit in filtered
    }

    # Exact repository-relative path mentions are high-confidence evidence.
    # They are still localization evidence, not mutation authorization.
    explicit_paths = _mentioned_repository_paths(
        clean_query,
        repository_paths,
    )
    for explicit_path in explicit_paths:
        if explicit_path in excluded_set:
            continue

        file = files_by_path.get(explicit_path)
        if file is None:
            continue

        existing = scored.get(explicit_path)
        explicit_score = max(
            EXACT_PATH_SCORE_FLOOR,
            (
                existing.score + EXACT_PATH_BONUS
                if existing is not None
                else EXACT_PATH_SCORE_FLOOR
            ),
        )

        scored[explicit_path] = LocalizationCandidate(
            path=explicit_path,
            score=round(explicit_score, 3),
            confidence="low",
            is_test=file.is_test,
            symbols=(
                existing.symbols
                if existing is not None
                else ()
            ),
            reasons=tuple(
                dict.fromkeys(
                    (
                        *(
                            existing.reasons
                            if existing is not None
                            else ()
                        ),
                        "localizer:explicit-path",
                    )
                )
            ),
            graph_related=(
                existing.graph_related
                if existing is not None
                else False
            ),
        )

    if not scored:
        return LocalizationResult(
            query=clean_query,
            candidates=(),
            likely_implementation_paths=(),
            affected_tests=(),
            dependencies=(),
            repository=RepositoryMap(
                file_count=profile.file_count,
                test_count=profile.test_count,
                languages=profile.languages,
                build_systems=profile.build_systems,
                recent_commits=tuple(
                    (item.commit, item.subject)
                    for item in profile.recent_commits
                ),
            ),
            excluded_paths=excluded,
        )

    implementation_seeds = tuple(
        sorted(
            (
                item
                for item in scored.values()
                if (
                    not item.is_test
                    and item.path.endswith(".py")
                    and item.path not in excluded_set
                )
            ),
            key=lambda item: (-item.score, item.path),
        )[:seed_limit]
    )

    dependencies: list[LocalizationDependency] = []
    try:
        graph = scan_python_dependency_graph(profile.root)
    except Exception:
        graph = None

    if graph is not None and implementation_seeds:
        seed_paths = tuple(item.path for item in implementation_seeds)
        seed_scores = {item.path: item.score for item in implementation_seeds}
        related = related_python_files(
            graph,
            seed_paths,
            max_hops=1,
            limit=graph_limit,
        )

        for item in related:
            if item.path in excluded_set:
                continue
            file = files_by_path.get(item.path)
            if file is None:
                continue
            seed_score = seed_scores.get(item.via_path, 0.0)
            bonus = max(3.0, seed_score * 0.55)
            if file.is_test:
                bonus += 5.0
            elif item.relation == "imported_by":
                bonus += 1.5

            existing = scored.get(item.path)
            if existing is not None:
                scored[item.path] = LocalizationCandidate(
                    path=existing.path,
                    score=round(existing.score + bonus, 3),
                    confidence="low",
                    is_test=existing.is_test,
                    symbols=existing.symbols,
                    reasons=tuple(
                        dict.fromkeys(
                            (
                                *existing.reasons,
                                f"localizer:{item.relation}:{item.via_path}",
                            )
                        )
                    ),
                    graph_related=True,
                )
            else:
                scored[item.path] = LocalizationCandidate(
                    path=item.path,
                    score=round(bonus, 3),
                    confidence="low",
                    is_test=file.is_test,
                    symbols=(),
                    reasons=(f"localizer:{item.relation}:{item.via_path}",),
                    graph_related=True,
                )

        candidate_paths = set(scored)
        for edge in graph.dependencies:
            if (
                edge.source_path in candidate_paths
                and edge.target_path in candidate_paths
            ):
                dependencies.append(
                    LocalizationDependency(
                        source_path=edge.source_path,
                        target_path=edge.target_path,
                        relation="imports",
                    )
                )

    # File-name affinity is deliberately applied after graph expansion so a
    # topologically discovered implementation file can surface its conventional
    # regression test even when that test is not represented in the import graph.
    affinity_sources = tuple(
        sorted(
            (
                item
                for item in scored.values()
                if (
                    not item.is_test
                    and item.path.endswith(".py")
                    and item.path not in excluded_set
                )
            ),
            key=lambda item: (-item.score, item.path),
        )[:DEFAULT_AFFINITY_SOURCE_LIMIT]
    )

    for source_candidate in affinity_sources:
        source = Path(source_candidate.path)
        source_terms = {
            source.stem.casefold(),
            source.parent.name.casefold(),
        }
        source_terms.discard("src")

        for test_path in profile.test_files:
            if test_path in excluded_set:
                continue

            test_terms = set(tokenize_query(test_path))
            overlap = source_terms & test_terms
            if source.stem.casefold() not in test_terms:
                continue

            bonus = (
                max(4.0, source_candidate.score * 0.4)
                + (2.0 * len(overlap))
            )
            existing = scored.get(test_path)
            if existing is not None:
                scored[test_path] = LocalizationCandidate(
                    path=existing.path,
                    score=round(existing.score + bonus, 3),
                    confidence="low",
                    is_test=True,
                    symbols=existing.symbols,
                    reasons=tuple(
                        dict.fromkeys(
                            (
                                *existing.reasons,
                                f"localizer:test-affinity:{source_candidate.path}",
                            )
                        )
                    ),
                    graph_related=True,
                )
            else:
                scored[test_path] = LocalizationCandidate(
                    path=test_path,
                    score=round(bonus, 3),
                    confidence="low",
                    is_test=True,
                    symbols=(),
                    reasons=(
                        f"localizer:test-affinity:{source_candidate.path}",
                    ),
                    graph_related=True,
                )

    ordered = sorted(
        (
            item
            for item in scored.values()
            if item.path not in excluded_set
        ),
        key=lambda item: (
            -item.score,
            0 if item.graph_related else 1,
            0 if not item.is_test else 1,
            item.path,
        ),
    )
    maximum = ordered[0].score if ordered else 0.0
    candidates = tuple(
        LocalizationCandidate(
            path=item.path,
            score=item.score,
            confidence=(
                "high"
                if "localizer:explicit-path" in item.reasons
                else _candidate_confidence(
                    item.score,
                    maximum,
                    item.graph_related,
                )
            ),
            is_test=item.is_test,
            symbols=item.symbols,
            reasons=item.reasons,
            graph_related=item.graph_related,
        )
        for item in ordered[:limit]
    )

    likely_implementation_paths = tuple(
        item.path
        for item in candidates
        if not item.is_test
    )[:5]
    affected_tests = tuple(
        item.path
        for item in candidates
        if item.is_test
    )[:5]

    return LocalizationResult(
        query=clean_query,
        candidates=candidates,
        likely_implementation_paths=likely_implementation_paths,
        affected_tests=affected_tests,
        dependencies=tuple(
            sorted(
                set(dependencies),
                key=lambda item: (
                    item.source_path,
                    item.target_path,
                    item.relation,
                ),
            )
        ),
        repository=RepositoryMap(
            file_count=profile.file_count,
            test_count=profile.test_count,
            languages=profile.languages,
            build_systems=profile.build_systems,
            recent_commits=tuple(
                (item.commit, item.subject)
                for item in profile.recent_commits
            ),
        ),
        excluded_paths=excluded,
    )

def localize_task(
    connection: sqlite3.Connection,
    task_id: str,
    *,
    limit: int = DEFAULT_LOCALIZATION_LIMIT,
) -> LocalizationResult:
    """Localize one persistent task inside its isolated worktree."""

    task = get_task(connection, task_id)
    if task is None:
        raise TaskNotFoundError(f"Unknown task: {task_id}")
    if not task.worktree_path:
        raise LocalizationError("Task has no isolated worktree.")

    query_parts = [task.title, task.request]
    if task.acceptance_criteria:
        query_parts.append(task.acceptance_criteria)

    return localize_repository(
        task.worktree_path,
        "\n".join(query_parts),
        limit=limit,
    )
