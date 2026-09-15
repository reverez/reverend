"""Deterministic Python structural intelligence."""

from __future__ import annotations

import ast
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from reverend.development import (
    TaskNotFoundError,
    get_task,
)

from .repository import (
    RepositoryIntelligenceError,
    scan_repository,
)


class PythonIntelligenceError(
    RepositoryIntelligenceError
):
    """Base Python structural-intelligence error."""


@dataclass(frozen=True)
class PythonSymbol:
    path: str
    module: str
    name: str
    qualified_name: str
    kind: str
    line_start: int
    line_end: int
    is_async: bool = False


@dataclass(frozen=True)
class PythonImport:
    path: str
    module: str
    imported_module: str | None
    imported_name: str | None
    alias: str | None
    level: int
    line: int


@dataclass(frozen=True)
class PythonCall:
    path: str
    module: str
    caller: str | None
    callee: str
    line: int


@dataclass(frozen=True)
class PythonFileProfile:
    path: str
    module: str
    symbols: tuple[PythonSymbol, ...]
    imports: tuple[PythonImport, ...]
    calls: tuple[PythonCall, ...]
    syntax_error: str | None

    @property
    def symbol_count(self) -> int:
        return len(self.symbols)

    @property
    def import_count(self) -> int:
        return len(self.imports)


@dataclass(frozen=True)
class PythonRepositoryProfile:
    root: Path
    files: tuple[PythonFileProfile, ...]

    @property
    def symbols(self) -> tuple[PythonSymbol, ...]:
        return tuple(
            symbol
            for file in self.files
            for symbol in file.symbols
        )

    @property
    def imports(self) -> tuple[PythonImport, ...]:
        return tuple(
            item
            for file in self.files
            for item in file.imports
        )

    @property
    def calls(self) -> tuple[PythonCall, ...]:
        return tuple(
            item
            for file in self.files
            for item in file.calls
        )

    @property
    def parse_errors(
        self,
    ) -> tuple[PythonFileProfile, ...]:
        return tuple(
            file
            for file in self.files
            if file.syntax_error is not None
        )


def module_name_for_path(
    relative_path: str,
) -> str:
    """Convert a repository-relative Python path into a module name."""

    path = Path(relative_path)

    parts = list(
        path.with_suffix("").parts
    )

    if (
        parts
        and parts[-1] == "__init__"
    ):
        parts.pop()

    if not parts:
        return "__root__"

    return ".".join(parts)


class _Visitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        path: str,
        module: str,
    ) -> None:
        self.path = path
        self.module = module

        self.symbols: list[
            PythonSymbol
        ] = []

        self.imports: list[
            PythonImport
        ] = []

        self.calls: list[
            PythonCall
        ] = []

        self._scope: list[
            tuple[str, str]
        ] = []

    def _qualified(
        self,
        name: str,
    ) -> str:
        names = [
            item[0]
            for item in self._scope
        ]

        names.append(name)

        return ".".join(names)

    def _symbol(
        self,
        node: (
            ast.ClassDef
            | ast.FunctionDef
            | ast.AsyncFunctionDef
        ),
        *,
        kind: str,
        is_async: bool = False,
    ) -> None:
        self.symbols.append(
            PythonSymbol(
                path=self.path,
                module=self.module,
                name=node.name,
                qualified_name=self._qualified(
                    node.name
                ),
                kind=kind,
                line_start=node.lineno,
                line_end=(
                    node.end_lineno
                    or node.lineno
                ),
                is_async=is_async,
            )
        )

    def visit_ClassDef(
        self,
        node: ast.ClassDef,
    ) -> None:
        self._symbol(
            node,
            kind="class",
        )

        self._scope.append(
            (
                node.name,
                "class",
            )
        )

        self.generic_visit(node)

        self._scope.pop()

    def visit_FunctionDef(
        self,
        node: ast.FunctionDef,
    ) -> None:
        parent_kind = (
            self._scope[-1][1]
            if self._scope
            else None
        )

        kind = (
            "method"
            if parent_kind == "class"
            else "function"
        )

        self._symbol(
            node,
            kind=kind,
        )

        self._scope.append(
            (
                node.name,
                kind,
            )
        )

        self.generic_visit(node)

        self._scope.pop()

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        parent_kind = (
            self._scope[-1][1]
            if self._scope
            else None
        )

        kind = (
            "method"
            if parent_kind == "class"
            else "function"
        )

        self._symbol(
            node,
            kind=kind,
            is_async=True,
        )

        self._scope.append(
            (
                node.name,
                kind,
            )
        )

        self.generic_visit(node)

        self._scope.pop()

    @staticmethod
    def _call_name(
        node: ast.expr,
    ) -> str | None:
        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            parent = _Visitor._call_name(
                node.value
            )

            if parent is None:
                return None

            return (
                f"{parent}.{node.attr}"
            )

        return None

    def visit_Call(
        self,
        node: ast.Call,
    ) -> None:
        callee = self._call_name(
            node.func
        )

        if callee:
            caller = (
                ".".join(
                    item[0]
                    for item in self._scope
                )
                or None
            )

            self.calls.append(
                PythonCall(
                    path=self.path,
                    module=self.module,
                    caller=caller,
                    callee=callee,
                    line=node.lineno,
                )
            )

        self.generic_visit(node)

    def visit_Import(
        self,
        node: ast.Import,
    ) -> None:
        for alias in node.names:
            self.imports.append(
                PythonImport(
                    path=self.path,
                    module=self.module,
                    imported_module=(
                        alias.name
                    ),
                    imported_name=None,
                    alias=alias.asname,
                    level=0,
                    line=node.lineno,
                )
            )

    def visit_ImportFrom(
        self,
        node: ast.ImportFrom,
    ) -> None:
        for alias in node.names:
            self.imports.append(
                PythonImport(
                    path=self.path,
                    module=self.module,
                    imported_module=(
                        node.module
                    ),
                    imported_name=(
                        alias.name
                    ),
                    alias=alias.asname,
                    level=node.level,
                    line=node.lineno,
                )
            )


def scan_python_file(
    root: str | Path,
    relative_path: str,
) -> PythonFileProfile:
    """Parse one repository-relative Python file."""

    repository_root = Path(
        root
    ).resolve()

    absolute = (
        repository_root
        / relative_path
    ).resolve()

    try:
        absolute.relative_to(
            repository_root
        )
    except ValueError as exc:
        raise PythonIntelligenceError(
            "Python source path escaped "
            f"repository root: {relative_path}"
        ) from exc

    if absolute.suffix.lower() != ".py":
        raise PythonIntelligenceError(
            "Not a Python source file: "
            f"{relative_path}"
        )

    module = module_name_for_path(
        relative_path
    )

    try:
        source = absolute.read_text(
            encoding="utf-8"
        )
    except (
        OSError,
        UnicodeError,
    ) as exc:
        raise PythonIntelligenceError(
            f"Unable to read {relative_path}: {exc}"
        ) from exc

    try:
        tree = ast.parse(
            source,
            filename=relative_path,
        )
    except SyntaxError as exc:
        location = (
            f"line {exc.lineno}"
            if exc.lineno
            else "unknown line"
        )

        return PythonFileProfile(
            path=relative_path,
            module=module,
            symbols=(),
            imports=(),
            calls=(),
            syntax_error=(
                f"{exc.msg} ({location})"
            ),
        )

    visitor = _Visitor(
        path=relative_path,
        module=module,
    )

    visitor.visit(tree)

    return PythonFileProfile(
        path=relative_path,
        module=module,
        symbols=tuple(
            visitor.symbols
        ),
        imports=tuple(
            visitor.imports
        ),
        calls=tuple(
            visitor.calls
        ),
        syntax_error=None,
    )


def scan_python_repository(
    path: str | Path,
) -> PythonRepositoryProfile:
    """Parse all visible, non-symlink Python files in a repository."""

    repository = scan_repository(
        path,
        history_limit=0,
    )

    profiles: list[
        PythonFileProfile
    ] = []

    for file in repository.files:
        if (
            file.language != "Python"
            or file.is_symlink
        ):
            continue

        profiles.append(
            scan_python_file(
                repository.root,
                file.path,
            )
        )

    return PythonRepositoryProfile(
        root=repository.root,
        files=tuple(profiles),
    )


def scan_task_python_repository(
    connection: sqlite3.Connection,
    task_id: str,
) -> PythonRepositoryProfile:
    """Parse Python structure from a task's isolated worktree."""

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if not task.worktree_path:
        raise PythonIntelligenceError(
            "Task has no isolated worktree."
        )

    return scan_python_repository(
        task.worktree_path
    )
