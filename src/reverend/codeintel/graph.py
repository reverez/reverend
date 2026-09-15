"""Bounded deterministic Python dependency graph for code localization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .python import (
    PythonImport,
    PythonRepositoryProfile,
    scan_python_repository,
)


@dataclass(frozen=True)
class PythonDependency:
    """One resolved repository-internal Python import edge."""

    source_path: str
    target_path: str
    source_module: str
    target_module: str
    imported_name: str | None
    line: int


@dataclass(frozen=True)
class PythonSymbolCall:
    """One conservatively resolved repository-internal call edge."""

    source_path: str
    source_symbol: str
    target_path: str
    target_symbol: str
    line: int


@dataclass(frozen=True)
class RelatedPythonFile:
    """A bounded graph neighbor reached from a localization seed."""

    path: str
    via_path: str
    relation: str
    distance: int


@dataclass(frozen=True)
class PythonDependencyGraph:
    root: Path
    files: tuple[str, ...]
    dependencies: tuple[PythonDependency, ...]
    symbol_calls: tuple[PythonSymbolCall, ...]

    def imports_from(
        self,
        path: str,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    edge.target_path
                    for edge in self.dependencies
                    if edge.source_path == path
                }
            )
        )

    def imported_by(
        self,
        path: str,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    edge.source_path
                    for edge in self.dependencies
                    if edge.target_path == path
                }
            )
        )


def _candidate_modules(
    source_module: str,
    item: PythonImport,
) -> tuple[str, ...]:
    """Return deterministic module candidates for one import statement."""

    if item.level:
        package = source_module.split(".")[:-1]
        ascend = item.level - 1

        if ascend > len(package):
            return ()

        base = (
            package[: len(package) - ascend]
            if ascend
            else package
        )

        if item.imported_module:
            base = [
                *base,
                *item.imported_module.split("."),
            ]

        module = ".".join(
            part
            for part in base
            if part
        )
    else:
        module = (
            item.imported_module
            or ""
        )

    candidates: list[str] = []

    if module and item.imported_name:
        candidates.append(
            f"{module}.{item.imported_name}"
        )
    elif item.imported_name:
        candidates.append(
            item.imported_name
        )

    if module:
        candidates.append(module)

    seen: set[str] = set()
    ordered: list[str] = []

    for candidate in candidates:
        if candidate in seen:
            continue

        seen.add(candidate)
        ordered.append(candidate)

    return tuple(ordered)


def build_python_dependency_graph(
    profile: PythonRepositoryProfile,
) -> PythonDependencyGraph:
    """Resolve repository-internal imports and conservative symbol calls."""

    module_to_path = {
        file.module: file.path
        for file in profile.files
        if file.syntax_error is None
    }
    top_symbols = {
        file.module: {
            symbol.name: symbol.qualified_name
            for symbol in file.symbols
            if "." not in symbol.qualified_name
        }
        for file in profile.files
        if file.syntax_error is None
    }
    qualified_by_path = {
        file.path: {
            symbol.qualified_name
            for symbol in file.symbols
        }
        for file in profile.files
        if file.syntax_error is None
    }

    edges: set[
        tuple[
            str,
            str,
            str,
            str,
            str | None,
            int,
        ]
    ] = set()
    calls: set[
        tuple[
            str,
            str,
            str,
            str,
            int,
        ]
    ] = set()

    for file in profile.files:
        if file.syntax_error is not None:
            continue

        symbol_bindings: dict[
            str,
            tuple[str, str],
        ] = {}
        module_bindings: dict[
            str,
            tuple[str, str],
        ] = {}

        for item in file.imports:
            target_module = None
            target_path = None

            for candidate in _candidate_modules(
                file.module,
                item,
            ):
                resolved = module_to_path.get(
                    candidate
                )

                if resolved is None:
                    continue

                target_module = candidate
                target_path = resolved
                break

            if (
                target_module is None
                or target_path is None
                or target_path == file.path
            ):
                continue

            edges.add(
                (
                    file.path,
                    target_path,
                    file.module,
                    target_module,
                    item.imported_name,
                    item.line,
                )
            )

            if item.imported_name:
                target_symbol = (
                    top_symbols
                    .get(
                        target_module,
                        {},
                    )
                    .get(
                        item.imported_name
                    )
                )

                local_name = (
                    item.alias
                    or item.imported_name
                )

                if target_symbol:
                    symbol_bindings[
                        local_name
                    ] = (
                        target_path,
                        target_symbol,
                    )
                elif (
                    target_module.endswith(
                        "." + item.imported_name
                    )
                ):
                    module_bindings[
                        local_name
                    ] = (
                        target_path,
                        target_module,
                    )
            else:
                binding = (
                    item.alias
                    or target_module
                )
                module_bindings[
                    binding
                ] = (
                    target_path,
                    target_module,
                )

        local_symbols = top_symbols.get(
            file.module,
            {},
        )

        for call in file.calls:
            if call.caller is None:
                continue

            target_path = None
            target_symbol = None

            if "." not in call.callee:
                local = local_symbols.get(
                    call.callee
                )

                if local:
                    target_path = file.path
                    target_symbol = local
                else:
                    imported = (
                        symbol_bindings.get(
                            call.callee
                        )
                    )

                    if imported:
                        (
                            target_path,
                            target_symbol,
                        ) = imported
            else:
                first, _, remainder = (
                    call.callee.partition(".")
                )

                if first in {
                    "self",
                    "cls",
                }:
                    class_name = (
                        call.caller.split(
                            "."
                        )[0]
                    )
                    candidate = (
                        f"{class_name}."
                        f"{remainder}"
                    )

                    if (
                        candidate
                        in qualified_by_path.get(
                            file.path,
                            set(),
                        )
                    ):
                        target_path = file.path
                        target_symbol = candidate
                else:
                    for binding, (
                        module_path,
                        module_name,
                    ) in module_bindings.items():
                        prefix = (
                            binding + "."
                        )

                        if not call.callee.startswith(
                            prefix
                        ):
                            continue

                        name = call.callee[
                            len(prefix):
                        ].split(".")[-1]

                        candidate = (
                            top_symbols
                            .get(
                                module_name,
                                {},
                            )
                            .get(name)
                        )

                        if candidate:
                            target_path = module_path
                            target_symbol = candidate
                            break

            if (
                target_path is None
                or target_symbol is None
            ):
                continue

            calls.add(
                (
                    file.path,
                    call.caller,
                    target_path,
                    target_symbol,
                    call.line,
                )
            )

    dependencies = tuple(
        PythonDependency(
            source_path=source_path,
            target_path=target_path,
            source_module=source_module,
            target_module=target_module,
            imported_name=imported_name,
            line=line,
        )
        for (
            source_path,
            target_path,
            source_module,
            target_module,
            imported_name,
            line,
        ) in sorted(edges)
    )
    symbol_calls = tuple(
        PythonSymbolCall(
            source_path=source_path,
            source_symbol=source_symbol,
            target_path=target_path,
            target_symbol=target_symbol,
            line=line,
        )
        for (
            source_path,
            source_symbol,
            target_path,
            target_symbol,
            line,
        ) in sorted(calls)
    )

    return PythonDependencyGraph(
        root=profile.root,
        files=tuple(
            sorted(
                file.path
                for file in profile.files
            )
        ),
        dependencies=dependencies,
        symbol_calls=symbol_calls,
    )

def scan_python_dependency_graph(
    path: str | Path,
) -> PythonDependencyGraph:
    """Build the dependency graph directly from a repository."""

    return build_python_dependency_graph(
        scan_python_repository(path)
    )


def related_python_files(
    graph: PythonDependencyGraph,
    seed_paths: tuple[str, ...] | list[str],
    *,
    max_hops: int = 1,
    limit: int = 12,
) -> tuple[RelatedPythonFile, ...]:
    """Return bounded forward/reverse dependency neighbors for localization."""

    if max_hops < 1 or max_hops > 4:
        raise ValueError(
            "max_hops must be between 1 and 4"
        )

    if limit < 1:
        raise ValueError(
            "limit must be positive"
        )

    valid = set(graph.files)
    seeds = tuple(
        dict.fromkeys(
            path
            for path in seed_paths
            if path in valid
        )
    )

    if not seeds:
        return ()

    forward: dict[str, set[str]] = {}
    reverse: dict[str, set[str]] = {}

    for edge in graph.dependencies:
        forward.setdefault(
            edge.source_path,
            set(),
        ).add(edge.target_path)

        reverse.setdefault(
            edge.target_path,
            set(),
        ).add(edge.source_path)

    seed_set = set(seeds)
    seen = set(seeds)
    frontier = list(seeds)
    related: list[RelatedPythonFile] = []

    for distance in range(
        1,
        max_hops + 1,
    ):
        next_frontier: list[str] = []

        # Preserve caller-supplied seed rank. The retrieval layer orders
        # seeds by direct relevance, so the first provenance recorded for a
        # multiply-related file should come from the strongest seed rather
        # than alphabetical path order. Neighbor order remains deterministic.
        for current in frontier:
            neighbors = [
                (path, "imports")
                for path in forward.get(
                    current,
                    set(),
                )
            ]

            neighbors.extend(
                (
                    path,
                    "imported_by",
                )
                for path in reverse.get(
                    current,
                    set(),
                )
            )

            for path, relation in sorted(
                neighbors,
                key=lambda item: (
                    item[0],
                    item[1],
                ),
            ):
                if (
                    path in seed_set
                    or path in seen
                ):
                    continue

                seen.add(path)
                next_frontier.append(path)
                related.append(
                    RelatedPythonFile(
                        path=path,
                        via_path=current,
                        relation=relation,
                        distance=distance,
                    )
                )

                if len(related) >= limit:
                    return tuple(related)

        frontier = next_frontier

        if not frontier:
            break

    return tuple(related)
