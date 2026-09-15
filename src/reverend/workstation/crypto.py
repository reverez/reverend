"""Audited authenticated encryption for Reverend workstation state."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from cryptography.fernet import (
    Fernet,
    InvalidToken,
)

from reverend.config import RUNTIME_CONFIG


ENCRYPTED_PREFIX = "fernet:v1:"


class StateEncryptionError(RuntimeError):
    """Raised when encrypted workstation state cannot be trusted or opened."""


def default_state_key_path() -> Path:
    explicit = os.environ.get(
        "REVEREND_STATE_KEY_FILE"
    )
    if explicit:
        return Path(explicit).expanduser()

    return (
        RUNTIME_CONFIG.parent
        / "state-v1.key"
    )


def _secure_parent(path: Path) -> None:
    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    if path.is_symlink():
        raise StateEncryptionError(
            "State-key directory cannot be a symlink."
        )

    try:
        os.chmod(
            path,
            0o700,
        )
    except OSError as exc:
        raise StateEncryptionError(
            f"Unable to secure state-key directory: {path}"
        ) from exc


def _validate_key_file(path: Path) -> None:
    if path.is_symlink():
        raise StateEncryptionError(
            "State key cannot be a symlink."
        )

    try:
        details = path.stat()
    except OSError as exc:
        raise StateEncryptionError(
            f"Unable to inspect state key: {path}"
        ) from exc

    if not stat.S_ISREG(
        details.st_mode
    ):
        raise StateEncryptionError(
            "State key must be a regular file."
        )

    if hasattr(
        os,
        "getuid",
    ) and details.st_uid != os.getuid():
        raise StateEncryptionError(
            "State key is not owned by the current user."
        )

    try:
        os.chmod(
            path,
            0o600,
        )
    except OSError as exc:
        raise StateEncryptionError(
            f"Unable to secure state key: {path}"
        ) from exc


def _create_key(path: Path) -> bytes:
    key = Fernet.generate_key()

    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
    )

    try:
        descriptor = os.open(
            path,
            flags,
            0o600,
        )
    except FileExistsError:
        _validate_key_file(
            path
        )
        return path.read_bytes().strip()
    except OSError as exc:
        raise StateEncryptionError(
            f"Unable to create state key: {path}"
        ) from exc

    try:
        payload = (
            key
            + b"\n"
        )
        written = 0

        while (
            written
            < len(payload)
        ):
            count = os.write(
                descriptor,
                payload[
                    written:
                ],
            )

            if count < 1:
                raise StateEncryptionError(
                    "State key write did not make progress."
                )

            written += count

        os.fsync(
            descriptor
        )
    finally:
        os.close(
            descriptor
        )

    _validate_key_file(
        path
    )

    return key


class StateCipher:
    """Versioned Fernet encryption for small persistent text payloads."""

    def __init__(
        self,
        key_path: str | Path,
    ):
        self.key_path = Path(
            key_path
        ).expanduser()

        _secure_parent(
            self.key_path.parent
        )

        if self.key_path.exists() or self.key_path.is_symlink():
            _validate_key_file(
                self.key_path
            )
            try:
                key = (
                    self.key_path
                    .read_bytes()
                    .strip()
                )
            except OSError as exc:
                raise StateEncryptionError(
                    f"Unable to read state key: {self.key_path}"
                ) from exc
        else:
            key = _create_key(
                self.key_path
            )

        try:
            self._fernet = Fernet(
                key
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise StateEncryptionError(
                "State key is invalid."
            ) from exc

    @staticmethod
    def is_encrypted(
        value: str,
    ) -> bool:
        return (
            isinstance(
                value,
                str,
            )
            and value.startswith(
                ENCRYPTED_PREFIX
            )
        )

    def encrypt(
        self,
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "Encrypted state value must be text."
            )

        token = self._fernet.encrypt(
            value.encode(
                "utf-8"
            )
        )

        return (
            ENCRYPTED_PREFIX
            + token.decode(
                "ascii"
            )
        )

    def decrypt(
        self,
        value: str,
        *,
        allow_legacy: bool = False,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise StateEncryptionError(
                "Encrypted state value is not text."
            )

        if not self.is_encrypted(
            value
        ):
            if allow_legacy:
                return value

            raise StateEncryptionError(
                "Persistent state payload is not encrypted."
            )

        token = value[
            len(
                ENCRYPTED_PREFIX
            ):
        ]

        try:
            plain = self._fernet.decrypt(
                token.encode(
                    "ascii"
                )
            )
        except (
            InvalidToken,
            UnicodeEncodeError,
        ) as exc:
            raise StateEncryptionError(
                "Persistent state authentication failed."
            ) from exc

        try:
            return plain.decode(
                "utf-8"
            )
        except UnicodeDecodeError as exc:
            raise StateEncryptionError(
                "Persistent state plaintext is not UTF-8."
            ) from exc
