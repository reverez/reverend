"""Deterministic structural and lexical code retrieval."""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from reverend.development import (
    TaskNotFoundError,
    get_task,
)

from .graph import (
    build_python_dependency_graph,
    related_python_files,
)
from .python import (
    PythonRepositoryProfile,
    PythonSymbol,
    scan_python_repository,
)
from .repository import (
    RepositoryFile,
    RepositoryProfile,
    scan_repository,
)


DEFAULT_RESULT_LIMIT = 10
DEFAULT_MAX_FILE_BYTES = 1_000_000
DEFAULT_MAX_MATCH_LINES = 8

# High-confidence developer vocabulary used to bridge natural-language
# engineering requests to conventional repository path names.
PATH_INTENT_TOKENS = frozenset(
    {
        "cli",
        "gui",
    }
)

PATH_INTENT_BONUS = 48.0


class CodeRetrievalError(RuntimeError):
    """Base deterministic code-retrieval error."""


@dataclass(frozen=True)
class CodeHit:
    path: str
    language: str | None
    is_test: bool
    score: float
    reasons: tuple[str, ...]
    symbols: tuple[str, ...]
    line_numbers: tuple[int, ...]


@dataclass(frozen=True)
class CodeSearchResult:
    query: str
    tokens: tuple[str, ...]
    hits: tuple[CodeHit, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(
            hit.path
            for hit in self.hits
        )


def tokenize_query(
    value: str,
) -> tuple[str, ...]:
    """Normalize prose, snake_case and CamelCase into search tokens."""

    expanded = re.sub(
        r"([a-z0-9])([A-Z])",
        r"\1 \2",
        value,
    )

    expanded = expanded.replace(
        "_",
        " ",
    )

    raw = re.findall(
        r"[A-Za-z0-9]+",
        expanded.lower(),
    )

    seen: set[str] = set()
    tokens: list[str] = []

    for token in raw:
        if len(token) < 2:
            continue

        if token in seen:
            continue

        seen.add(token)
        tokens.append(token)

    normalized_phrase = " ".join(raw)

    aliases: list[str] = []

    # Natural engineering language -> conventional repository terms.
    if "command line" in normalized_phrase:
        aliases.append("cli")

    if "graphical user interface" in normalized_phrase:
        aliases.append("gui")

    if "configuration" in seen:
        aliases.append("config")

    if "documentation" in seen:
        aliases.append("docs")

    for alias in aliases:
        if alias in seen:
            continue

        seen.add(alias)
        tokens.append(alias)

    return tuple(tokens)


def _normalized_words(
    value: str,
) -> set[str]:
    return set(
        tokenize_query(value)
    )


def _safe_read_text(
    root: Path,
    file: RepositoryFile,
    *,
    max_file_bytes: int,
) -> str | None:
    if file.is_symlink:
        return None

    if file.size_bytes > max_file_bytes:
        return None

    path = (
        root
        / file.path
    ).resolve()

    try:
        path.relative_to(root)
    except ValueError:
        return None

    try:
        raw = path.read_bytes()
    except OSError:
        return None

    if b"\0" in raw[:8192]:
        return None

    return raw.decode(
        "utf-8",
        errors="replace",
    )


def _symbol_map(
    profile: PythonRepositoryProfile,
) -> dict[str, list[PythonSymbol]]:
    result: dict[
        str,
        list[PythonSymbol],
    ] = defaultdict(list)

    for symbol in profile.symbols:
        result[
            symbol.path
        ].append(symbol)

    return result


def _score_path(
    path: str,
    tokens: tuple[str, ...],
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    path_lower = path.lower()
    path_words = _normalized_words(
        path
    )

    matched = [
        token
        for token in tokens
        if token in path_words
    ]

    if matched:
        score += (
            4.0
            * len(matched)
        )

        reasons.append(
            "path:"
            + ",".join(matched)
        )

        intent_matches = [
            token
            for token in matched
            if token in PATH_INTENT_TOKENS
        ]

        if intent_matches:
            score += (
                PATH_INTENT_BONUS
                * len(intent_matches)
            )

            reasons.append(
                "path-intent:"
                + ",".join(intent_matches)
            )

    filename = (
        Path(path)
        .stem
        .lower()
    )

    filename_words = (
        _normalized_words(
            filename
        )
    )

    filename_matches = [
        token
        for token in tokens
        if token in filename_words
    ]

    if filename_matches:
        score += (
            3.0
            * len(filename_matches)
        )

        reasons.append(
            "filename:"
            + ",".join(
                filename_matches
            )
        )

    phrase = " ".join(
        tokens
    )

    if (
        phrase
        and phrase.replace(
            " ",
            "_",
        ) in path_lower
    ):
        score += 3.0

    return score, reasons


def _score_symbols(
    symbols: list[PythonSymbol],
    tokens: tuple[str, ...],
) -> tuple[
    float,
    list[str],
    list[str],
]:
    score = 0.0
    reasons: list[str] = []
    matched_symbols: list[str] = []

    query_set = set(
        tokens
    )

    for symbol in symbols:
        symbol_words = (
            _normalized_words(
                symbol.qualified_name
            )
        )

        overlap = (
            query_set
            & symbol_words
        )

        if not overlap:
            continue

        weight = (
            6.0
            if symbol.kind
            in {
                "class",
                "function",
            }
            else 5.0
        )

        score += (
            weight
            * len(overlap)
        )

        matched_symbols.append(
            symbol.qualified_name
        )

    if matched_symbols:
        reasons.append(
            "symbols:"
            + ",".join(
                matched_symbols[:6]
            )
        )

    return (
        score,
        reasons,
        matched_symbols,
    )


def _score_content(
    text: str,
    tokens: tuple[str, ...],
    *,
    max_match_lines: int,
) -> tuple[
    float,
    list[str],
    list[int],
]:
    score = 0.0
    reasons: list[str] = []
    line_numbers: list[int] = []

    lower = text.lower()

    token_counts: dict[
        str,
        int,
    ] = {}

    for token in tokens:
        count = lower.count(
            token
        )

        if count:
            token_counts[
                token
            ] = count

            score += min(
                float(count),
                5.0,
            )

    if token_counts:
        reasons.append(
            "content:"
            + ",".join(
                f"{token}={count}"
                for token, count
                in token_counts.items()
            )
        )

        query_set = set(
            token_counts
        )

        for number, line in enumerate(
            text.splitlines(),
            start=1,
        ):
            line_words = (
                _normalized_words(
                    line
                )
            )

            if (
                query_set
                & line_words
            ):
                line_numbers.append(
                    number
                )

                if (
                    len(line_numbers)
                    >= max_match_lines
                ):
                    break

    phrase = " ".join(
        tokens
    )

    if (
        len(tokens) > 1
        and phrase in lower
    ):
        score += 4.0
        reasons.append(
            "exact-phrase"
        )

    return (
        score,
        reasons,
        line_numbers,
    )


def search_code(
    path: str | Path,
    query: str,
    *,
    limit: int = DEFAULT_RESULT_LIMIT,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_match_lines: int = DEFAULT_MAX_MATCH_LINES,
) -> CodeSearchResult:
    """Rank repository files using deterministic path, symbol and text evidence."""

    clean_query = query.strip()

    if not clean_query:
        raise CodeRetrievalError(
            "Search query cannot be empty."
        )

    if limit < 1:
        raise CodeRetrievalError(
            "Result limit must be positive."
        )

    if max_file_bytes < 1:
        raise CodeRetrievalError(
            "max_file_bytes must be positive."
        )

    repository: RepositoryProfile = (
        scan_repository(
            path,
            history_limit=0,
        )
    )

    python_profile = (
        scan_python_repository(
            repository.root
        )
    )

    symbols_by_path = (
        _symbol_map(
            python_profile
        )
    )

    tokens = tokenize_query(
        clean_query
    )

    if not tokens:
        raise CodeRetrievalError(
            "Search query contains no usable tokens."
        )

    changed = set(
        repository.changed_files
    )

    scored: list[
        CodeHit
    ] = []

    for file in repository.files:
        score = 0.0
        reasons: list[str] = []
        matched_symbols: list[str] = []
        line_numbers: list[int] = []

        path_score, path_reasons = (
            _score_path(
                file.path,
                tokens,
            )
        )

        score += path_score
        reasons.extend(
            path_reasons
        )

        file_symbols = (
            symbols_by_path.get(
                file.path,
                [],
            )
        )

        (
            symbol_score,
            symbol_reasons,
            matched_symbols,
        ) = _score_symbols(
            file_symbols,
            tokens,
        )

        score += symbol_score
        reasons.extend(
            symbol_reasons
        )

        text = _safe_read_text(
            repository.root,
            file,
            max_file_bytes=(
                max_file_bytes
            ),
        )

        if text is not None:
            (
                content_score,
                content_reasons,
                line_numbers,
            ) = _score_content(
                text,
                tokens,
                max_match_lines=(
                    max_match_lines
                ),
            )

            score += content_score
            reasons.extend(
                content_reasons
            )

        if (
            file.path
            in changed
            and score > 0
        ):
            score += 1.5
            reasons.append(
                "changed-file"
            )

        if file.is_test:
            if (
                "test" in tokens
                or "tests" in tokens
                or "spec" in tokens
                or "verify" in tokens
                or "verification" in tokens
            ):
                score += 2.0
                reasons.append(
                    "test-intent"
                )
            elif score > 0:
                # Implementation files should normally lead
                # engineering queries. Tests remain highly
                # relevant, but should not win merely because
                # names such as test_task_state_transition
                # contain every query token.
                score *= 0.75
                reasons.append(
                    "test-demotion"
                )

        if score <= 0:
            continue

        scored.append(
            CodeHit(
                path=file.path,
                language=file.language,
                is_test=file.is_test,
                score=round(
                    score,
                    3,
                ),
                reasons=tuple(
                    reasons
                ),
                symbols=tuple(
                    matched_symbols
                ),
                line_numbers=tuple(
                    line_numbers
                ),
            )
        )

    # M12: expand only from the strongest direct Python matches through
    # repository-internal import edges. The graph is deterministic, one-hop by
    # default and never makes semantic vectors authoritative over live text.
    direct = sorted(
        scored,
        key=lambda hit: (
            -hit.score,
            hit.path,
        ),
    )

    implementation_hits = tuple(
        hit
        for hit in direct
        if (
            hit.path.endswith(".py")
            and not hit.is_test
        )
    )

    if implementation_hits:
        seed_floor = max(
            1.0,
            implementation_hits[0].score
            * 0.25,
        )

        python_seeds = tuple(
            hit.path
            for hit in implementation_hits
            if hit.score >= seed_floor
        )[:3]
    else:
        python_seeds = ()

    if python_seeds:
        graph = build_python_dependency_graph(
            python_profile
        )
        related = related_python_files(
            graph,
            python_seeds,
            max_hops=1,
            limit=max(
                8,
                limit * 2,
            ),
        )
        files_by_path = {
            file.path: file
            for file in repository.files
        }
        scores_by_path = {
            hit.path: hit.score
            for hit in direct
        }
        hits_by_path = {
            hit.path: hit
            for hit in direct
        }

        for item in related:
            file = files_by_path.get(
                item.path
            )
            if file is None:
                continue

            seed_score = scores_by_path.get(
                item.via_path,
                0.0,
            )
            bonus = min(
                6.0,
                max(
                    2.0,
                    seed_score * 0.25,
                ),
            )

            if item.relation == "imported_by":
                bonus += 0.5

            if (
                file.is_test
                and not {
                    "test",
                    "tests",
                    "spec",
                    "verify",
                    "verification",
                }.intersection(tokens)
            ):
                bonus *= 0.85

            related_symbols: list[str] = []
            related_lines: list[int] = []
            call_reasons: list[str] = []

            for call in graph.symbol_calls:
                if (
                    item.relation == "imports"
                    and call.source_path
                    == item.via_path
                    and call.target_path
                    == item.path
                ):
                    related_symbols.append(
                        call.target_symbol
                    )
                    call_reasons.append(
                        "call:"
                        f"{call.source_symbol}->"
                        f"{call.target_symbol}"
                    )

                elif (
                    item.relation == "imported_by"
                    and call.source_path
                    == item.path
                    and call.target_path
                    == item.via_path
                ):
                    related_symbols.append(
                        call.source_symbol
                    )
                    related_lines.append(
                        call.line
                    )
                    call_reasons.append(
                        "call:"
                        f"{call.source_symbol}->"
                        f"{call.target_symbol}"
                    )

            reason = (
                f"graph:{item.relation}:"
                f"{item.via_path}:"
                f"distance={item.distance}"
            )
            existing = hits_by_path.get(
                item.path
            )

            if existing is None:
                hit = CodeHit(
                    path=file.path,
                    language=file.language,
                    is_test=file.is_test,
                    score=round(
                        bonus,
                        3,
                    ),
                    reasons=(
                        reason,
                        *tuple(
                            dict.fromkeys(
                                call_reasons
                            )
                        ),
                    ),
                    symbols=tuple(
                        dict.fromkeys(
                            related_symbols
                        )
                    ),
                    line_numbers=tuple(
                        dict.fromkeys(
                            related_lines
                        )
                    ),
                )
            else:
                # Existing direct hits keep their direct score. Graph
                # structure enriches provenance and focusing metadata, but
                # must not let a related test overtake the implementation
                # merely because it was also reachable from a seed.
                hit = CodeHit(
                    path=existing.path,
                    language=existing.language,
                    is_test=existing.is_test,
                    score=existing.score,
                    reasons=tuple(
                        dict.fromkeys(
                            (
                                *existing.reasons,
                                reason,
                                *call_reasons,
                            )
                        )
                    ),
                    symbols=tuple(
                        dict.fromkeys(
                            (
                                *existing.symbols,
                                *related_symbols,
                            )
                        )
                    ),
                    line_numbers=tuple(
                        dict.fromkeys(
                            (
                                *existing.line_numbers,
                                *related_lines,
                            )
                        )
                    ),
                )

            hits_by_path[
                item.path
            ] = hit

        scored = list(
            hits_by_path.values()
        )

    scored.sort(
        key=lambda hit: (
            -hit.score,
            hit.path,
        )
    )

    return CodeSearchResult(
        query=clean_query,
        tokens=tokens,
        hits=tuple(
            scored[:limit]
        ),
    )


def search_task_code(
    connection: sqlite3.Connection,
    task_id: str,
    query: str,
    *,
    limit: int = DEFAULT_RESULT_LIMIT,
) -> CodeSearchResult:
    """Search inside a task's isolated worktree."""

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if not task.worktree_path:
        raise CodeRetrievalError(
            "Task has no isolated worktree."
        )

    return search_code(
        task.worktree_path,
        query,
        limit=limit,
    )
