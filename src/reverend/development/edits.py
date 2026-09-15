"""Safe structured file-edit application for Reverend."""

from __future__ import annotations

import difflib
import hashlib
import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .models import TaskState
from .tasks import (
    TaskNotFoundError,
    get_task,
)


DEFAULT_MAX_FILE_BYTES = 512 * 1024
DEFAULT_MAX_TOTAL_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_DIFF_CHARS = 200_000

_ALLOWED_ACTIONS = {
    "create",
    "replace",
    "delete",
}


class EditError(RuntimeError):
    """Base error for Reverend structured edits."""


class EditValidationError(EditError):
    """Raised before mutation when an edit is unsafe or invalid."""


class EditPathError(EditValidationError):
    """Raised when an edit path violates repository containment."""


class EditConflictError(EditValidationError):
    """Raised when file-state preconditions no longer hold."""


class EditLimitError(EditValidationError):
    """Raised when a proposed edit exceeds configured limits."""


class EditStateError(EditValidationError):
    """Raised when the task/worktree cannot safely accept edits."""


class EditApplyError(EditError):
    """Raised when application fails and rollback is attempted."""


@dataclass(frozen=True)
class EditProposal:
    path: str
    action: str
    content: str | None = None
    expected_sha256: str | None = None


@dataclass(frozen=True)
class AppliedEdit:
    path: str
    action: str
    before_sha256: str | None
    after_sha256: str | None
    bytes_written: int


@dataclass(frozen=True)
class EditBatchResult:
    edits: tuple[AppliedEdit, ...]
    diff: str

    @property
    def changed_paths(self) -> tuple[str, ...]:
        return tuple(
            edit.path
            for edit in self.edits
        )


@dataclass
class _ValidatedEdit:
    proposal: EditProposal
    path: Path
    before_bytes: bytes | None
    before_mode: int | None
    before_sha256: str | None
    after_bytes: bytes | None
    after_sha256: str | None


def sha256_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def hash_file(
    path: str | Path,
) -> str:
    file_path = Path(path)

    if (
        not file_path.is_file()
        or file_path.is_symlink()
    ):
        raise EditValidationError(
            f"Not a regular file: {file_path}"
        )

    return sha256_bytes(
        file_path.read_bytes()
    )


def _validate_hash(
    value: str,
) -> str:
    clean = value.strip().lower()

    if len(clean) != 64:
        raise EditValidationError(
            "expected_sha256 must contain "
            "exactly 64 hexadecimal characters."
        )

    try:
        int(
            clean,
            16,
        )
    except ValueError as exc:
        raise EditValidationError(
            "expected_sha256 is not hexadecimal."
        ) from exc

    return clean


def _normalize_relative_path(
    value: str,
) -> Path:
    clean = value.strip()

    if not clean:
        raise EditPathError(
            "Edit path cannot be empty."
        )

    path = Path(clean)

    if path.is_absolute():
        raise EditPathError(
            f"Absolute edit path rejected: {clean}"
        )

    if ".." in path.parts:
        raise EditPathError(
            f"Parent traversal rejected: {clean}"
        )

    if any(
        part in {".git", ".reverend-build"}
        for part in path.parts
    ):
        raise EditPathError(
            f"Git/build control directory edits are forbidden: {clean}"
        )

    normalized = Path(
        *[
            part
            for part in path.parts
            if part not in {
                "",
                ".",
            }
        ]
    )

    if str(normalized) in {
        "",
        ".",
    }:
        raise EditPathError(
            "Edit path cannot target repository root."
        )

    return normalized


def _safe_target(
    root: Path,
    relative: Path,
) -> Path:
    current = root

    for part in relative.parts[:-1]:
        current = (
            current
            / part
        )

        if current.exists():
            if current.is_symlink():
                raise EditPathError(
                    "Symlink parent rejected: "
                    f"{current}"
                )

            if not current.is_dir():
                raise EditPathError(
                    "Edit parent is not a directory: "
                    f"{current}"
                )

    target = (
        root
        / relative
    )

    if (
        target.exists()
        and target.is_symlink()
    ):
        raise EditPathError(
            f"Symlink target rejected: {target}"
        )

    try:
        target.resolve(
            strict=False
        ).relative_to(
            root
        )
    except ValueError as exc:
        raise EditPathError(
            "Edit target escaped task worktree."
        ) from exc

    return target


def _decode_existing(
    raw: bytes,
    *,
    path: str,
) -> str:
    try:
        return raw.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise EditValidationError(
            "Structured edits currently support "
            f"UTF-8 text files only: {path}"
        ) from exc


def _atomic_write(
    path: Path,
    content: bytes,
    *,
    mode: int | None = None,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary = (
        tempfile.mkstemp(
            prefix=".reverend-edit-",
            dir=str(
                path.parent
            ),
        )
    )

    temporary_path = Path(
        temporary
    )

    try:
        with os.fdopen(
            descriptor,
            "wb",
        ) as handle:
            handle.write(
                content
            )
            handle.flush()
            os.fsync(
                handle.fileno()
            )

        if mode is not None:
            os.chmod(
                temporary_path,
                mode,
            )

        os.replace(
            temporary_path,
            path,
        )

    except BaseException:
        try:
            temporary_path.unlink(
                missing_ok=True
            )
        except OSError:
            pass

        raise


def _make_diff(
    edit: _ValidatedEdit,
) -> str:
    before_text = (
        ""
        if edit.before_bytes is None
        else _decode_existing(
            edit.before_bytes,
            path=edit.proposal.path,
        )
    )

    after_text = (
        ""
        if edit.after_bytes is None
        else edit.after_bytes.decode(
            "utf-8"
        )
    )

    before_lines = (
        before_text.splitlines(
            keepends=True
        )
    )

    after_lines = (
        after_text.splitlines(
            keepends=True
        )
    )

    return "".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=(
                "/dev/null"
                if edit.before_bytes is None
                else f"a/{edit.proposal.path}"
            ),
            tofile=(
                "/dev/null"
                if edit.after_bytes is None
                else f"b/{edit.proposal.path}"
            ),
            lineterm="\n",
        )
    )


def _git_diff_check(
    root: Path,
) -> None:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "diff",
                "--check",
                "--",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30.0,
            check=False,
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
    ) as exc:
        raise EditApplyError(
            f"Unable to run git diff --check: {exc}"
        ) from exc

    if result.returncode != 0:
        detail = (
            result.stdout.strip()
            or result.stderr.strip()
            or (
                "git diff --check "
                f"returned {result.returncode}"
            )
        )

        raise EditApplyError(
            "Applied edits failed Git whitespace "
            f"validation: {detail}"
        )


def _validate_proposals(
    root: Path,
    proposals: Sequence[EditProposal],
    *,
    max_file_bytes: int,
    max_total_bytes: int,
    max_diff_chars: int,
) -> tuple[
    list[_ValidatedEdit],
    str,
]:
    if not proposals:
        raise EditValidationError(
            "Edit batch cannot be empty."
        )

    seen: set[str] = set()
    validated: list[
        _ValidatedEdit
    ] = []

    total_output = 0

    for proposal in proposals:
        action = (
            proposal.action
            .strip()
            .lower()
        )

        if action not in _ALLOWED_ACTIONS:
            raise EditValidationError(
                "Unsupported edit action "
                f"{proposal.action!r}."
            )

        relative = (
            _normalize_relative_path(
                proposal.path
            )
        )

        normalized = (
            relative.as_posix()
        )

        if normalized in seen:
            raise EditValidationError(
                "Duplicate edit path: "
                f"{normalized}"
            )

        seen.add(
            normalized
        )

        target = _safe_target(
            root,
            relative,
        )

        exists = (
            target.exists()
        )

        before_bytes: (
            bytes | None
        ) = None

        before_mode: (
            int | None
        ) = None

        before_hash: (
            str | None
        ) = None

        if exists:
            if not target.is_file():
                raise EditValidationError(
                    "Structured edits can only "
                    f"target regular files: {normalized}"
                )

            size = (
                target.stat()
                .st_size
            )

            if size > max_file_bytes:
                raise EditLimitError(
                    f"Existing file exceeds limit: "
                    f"{normalized} ({size} bytes)"
                )

            before_bytes = (
                target.read_bytes()
            )

            _decode_existing(
                before_bytes,
                path=normalized,
            )

            before_mode = (
                stat.S_IMODE(
                    target.stat()
                    .st_mode
                )
            )

            before_hash = (
                sha256_bytes(
                    before_bytes
                )
            )

        after_bytes: (
            bytes | None
        )

        after_hash: (
            str | None
        )

        if action == "create":
            if exists:
                raise EditConflictError(
                    "Create would overwrite an "
                    f"existing file: {normalized}"
                )

            if proposal.expected_sha256 is not None:
                raise EditValidationError(
                    "Create edits must not specify "
                    "expected_sha256."
                )

            if not isinstance(
                proposal.content,
                str,
            ):
                raise EditValidationError(
                    "Create edit requires text content."
                )

            after_bytes = (
                proposal.content.encode(
                    "utf-8"
                )
            )

        elif action == "replace":
            if not exists:
                raise EditConflictError(
                    "Replace target does not exist: "
                    f"{normalized}"
                )

            if proposal.expected_sha256 is None:
                raise EditConflictError(
                    "Replace requires expected_sha256: "
                    f"{normalized}"
                )

            expected = _validate_hash(
                proposal.expected_sha256
            )

            if expected != before_hash:
                raise EditConflictError(
                    "File changed since model context "
                    f"was produced: {normalized}"
                )

            if not isinstance(
                proposal.content,
                str,
            ):
                raise EditValidationError(
                    "Replace edit requires text content."
                )

            after_bytes = (
                proposal.content.encode(
                    "utf-8"
                )
            )

        else:
            if not exists:
                raise EditConflictError(
                    "Delete target does not exist: "
                    f"{normalized}"
                )

            if proposal.expected_sha256 is None:
                raise EditConflictError(
                    "Delete requires expected_sha256: "
                    f"{normalized}"
                )

            expected = _validate_hash(
                proposal.expected_sha256
            )

            if expected != before_hash:
                raise EditConflictError(
                    "File changed since model context "
                    f"was produced: {normalized}"
                )

            if proposal.content is not None:
                raise EditValidationError(
                    "Delete edit must not include content."
                )

            after_bytes = None

        if (
            after_bytes is not None
            and len(after_bytes)
            > max_file_bytes
        ):
            raise EditLimitError(
                "Proposed file exceeds per-file "
                f"limit: {normalized}"
            )

        bytes_written = (
            0
            if after_bytes is None
            else len(after_bytes)
        )

        total_output += (
            bytes_written
        )

        if total_output > max_total_bytes:
            raise EditLimitError(
                "Edit batch exceeds total "
                "write-size limit."
            )

        after_hash = (
            None
            if after_bytes is None
            else sha256_bytes(
                after_bytes
            )
        )

        validated.append(
            _ValidatedEdit(
                proposal=EditProposal(
                    path=normalized,
                    action=action,
                    content=proposal.content,
                    expected_sha256=(
                        proposal.expected_sha256
                    ),
                ),
                path=target,
                before_bytes=before_bytes,
                before_mode=before_mode,
                before_sha256=(
                    before_hash
                ),
                after_bytes=after_bytes,
                after_sha256=(
                    after_hash
                ),
            )
        )

    diff = "".join(
        _make_diff(
            edit
        )
        for edit in validated
    )

    if len(diff) > max_diff_chars:
        raise EditLimitError(
            "Generated edit diff exceeds "
            "configured diff-size limit."
        )

    return (
        validated,
        diff,
    )


def _missing_parent_dirs(
    root: Path,
    path: Path,
) -> list[Path]:
    missing: list[
        Path
    ] = []

    current = path.parent

    while (
        current != root
        and not current.exists()
    ):
        missing.append(
            current
        )

        current = (
            current.parent
        )

    return list(
        reversed(
            missing
        )
    )


def _rollback(
    validated: Sequence[_ValidatedEdit],
    created_dirs: Sequence[Path],
) -> list[str]:
    errors: list[str] = []

    for edit in reversed(
        validated
    ):
        try:
            if edit.before_bytes is None:
                if edit.path.exists():
                    if edit.path.is_symlink():
                        raise RuntimeError(
                            "rollback target became symlink"
                        )

                    edit.path.unlink()

            else:
                _atomic_write(
                    edit.path,
                    edit.before_bytes,
                    mode=(
                        edit.before_mode
                    ),
                )

        except Exception as exc:
            errors.append(
                f"{edit.proposal.path}: {exc}"
            )

    for directory in reversed(
        created_dirs
    ):
        try:
            directory.rmdir()
        except OSError:
            pass

    return errors


def apply_edits(
    connection,
    task_id: str,
    proposals: Sequence[EditProposal],
    *,
    max_file_bytes: int = (
        DEFAULT_MAX_FILE_BYTES
    ),
    max_total_bytes: int = (
        DEFAULT_MAX_TOTAL_BYTES
    ),
    max_diff_chars: int = (
        DEFAULT_MAX_DIFF_CHARS
    ),
) -> EditBatchResult:
    """Validate and apply one structured edit batch to a task worktree."""

    if max_file_bytes < 1:
        raise EditLimitError(
            "max_file_bytes must be positive."
        )

    if max_total_bytes < 1:
        raise EditLimitError(
            "max_total_bytes must be positive."
        )

    if max_diff_chars < 1:
        raise EditLimitError(
            "max_diff_chars must be positive."
        )

    task = get_task(
        connection,
        task_id,
    )

    if task is None:
        raise TaskNotFoundError(
            f"Unknown task: {task_id}"
        )

    if task.state != TaskState.RUNNING:
        raise EditStateError(
            "Task must be RUNNING before "
            "structured edits may be applied."
        )

    if not task.worktree_path:
        raise EditStateError(
            "Task has no isolated worktree."
        )

    root = Path(
        task.worktree_path
    ).resolve()

    if not root.is_dir():
        raise EditStateError(
            f"Task worktree does not exist: {root}"
        )

    validated, diff = (
        _validate_proposals(
            root,
            proposals,
            max_file_bytes=(
                max_file_bytes
            ),
            max_total_bytes=(
                max_total_bytes
            ),
            max_diff_chars=(
                max_diff_chars
            ),
        )
    )

    created_dirs: list[
        Path
    ] = []

    try:
        for edit in validated:
            for directory in (
                _missing_parent_dirs(
                    root,
                    edit.path,
                )
            ):
                directory.mkdir()
                created_dirs.append(
                    directory
                )

            if (
                edit.proposal.action
                in {
                    "create",
                    "replace",
                }
            ):
                assert (
                    edit.after_bytes
                    is not None
                )

                mode = (
                    edit.before_mode
                    if edit.before_mode
                    is not None
                    else 0o644
                )

                _atomic_write(
                    edit.path,
                    edit.after_bytes,
                    mode=mode,
                )

            elif (
                edit.proposal.action
                == "delete"
            ):
                edit.path.unlink()

        _git_diff_check(
            root
        )

    except BaseException as exc:
        rollback_errors = (
            _rollback(
                validated,
                created_dirs,
            )
        )

        if rollback_errors:
            raise EditApplyError(
                "Edit application failed and "
                "rollback was incomplete. "
                f"Original error: {exc}. "
                "Rollback errors: "
                + "; ".join(
                    rollback_errors
                )
            ) from exc

        if isinstance(
            exc,
            EditError,
        ):
            raise

        raise EditApplyError(
            "Edit application failed; "
            "the batch was rolled back: "
            f"{exc}"
        ) from exc

    applied = tuple(
        AppliedEdit(
            path=edit.proposal.path,
            action=edit.proposal.action,
            before_sha256=(
                edit.before_sha256
            ),
            after_sha256=(
                edit.after_sha256
            ),
            bytes_written=(
                0
                if edit.after_bytes
                is None
                else len(
                    edit.after_bytes
                )
            ),
        )
        for edit in validated
    )

    return EditBatchResult(
        edits=applied,
        diff=diff,
    )
