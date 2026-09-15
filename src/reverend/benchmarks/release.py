"""Portable clean-checkout packaging and startup smoke for M15."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import venv
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from reverend import __version__


_REQUIRED_WHEEL_PATHS = {
    "reverend/__init__.py",
    "reverend/cli.py",
    "reverend/config.py",
    "reverend/workstation/server.py",
    "reverend/workstation/service.py",
    "reverend/ui/index.html",
    "reverend/ui/app.js",
    "reverend/ui/app.css",
    "reverend/ui/sources.js",
}


class ReleaseSmokeError(RuntimeError):
    """Raised when the committed release candidate cannot package/start cleanly."""


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )

    if completed.returncode != 0:
        raise ReleaseSmokeError(
            "Release smoke command failed: "
            + " ".join(argv)
            + "\n"
            + (completed.stdout or "")[-2000:]
            + (completed.stderr or "")[-2000:]
        )

    return completed


def _tracked_worktree_changes(
    repository: Path,
) -> list[str]:
    status = _run(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=no",
        ],
        cwd=repository,
    ).stdout

    return [
        line
        for line
        in status.splitlines()
        if line.strip()
    ]


def _clean_head_archive(
    repository: Path,
    destination: Path,
) -> tuple[str, list[str]]:
    tracked_changes = _tracked_worktree_changes(
        repository
    )

    revision = _run(
        [
            "git",
            "rev-parse",
            "HEAD",
        ],
        cwd=repository,
    ).stdout.strip()

    archive = subprocess.run(
        [
            "git",
            "archive",
            "--format=tar",
            "HEAD",
        ],
        cwd=repository,
        capture_output=True,
        timeout=30,
        check=False,
    )

    if archive.returncode != 0:
        raise ReleaseSmokeError(
            "Unable to create clean HEAD archive."
        )

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tarfile.open(
        fileobj=io.BytesIO(
            archive.stdout
        ),
        mode="r:",
    ) as handle:
        for member in handle.getmembers():
            target = (
                destination
                / member.name
            ).resolve()

            if not target.is_relative_to(
                destination.resolve()
            ):
                raise ReleaseSmokeError(
                    "Git archive contains an unsafe path."
                )

        handle.extractall(
            destination
        )

    return (
        revision,
        tracked_changes,
    )


def _build_wheel(
    source: Path,
    wheel_dir: Path,
) -> Path:
    wheel_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        import setuptools.build_meta  # noqa: F401
        import wheel  # noqa: F401
    except ImportError as exc:
        raise ReleaseSmokeError(
            "Release build prerequisites are missing from the active "
            "environment. Refresh it with: "
            "python -m pip install -e '.[dev]'"
        ) from exc

    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(
                wheel_dir
            ),
            ".",
        ],
        cwd=source,
        timeout=180,
    )

    wheels = sorted(
        wheel_dir.glob(
            "reverend-*.whl"
        )
    )

    if len(wheels) != 1:
        raise ReleaseSmokeError(
            "Expected exactly one Reverend wheel."
        )

    return wheels[0]


def _inspect_wheel(
    wheel: Path,
) -> dict:
    with zipfile.ZipFile(
        wheel
    ) as archive:
        names = set(
            archive.namelist()
        )

    missing = sorted(
        _REQUIRED_WHEEL_PATHS
        - names
    )

    version_marker = (
        f"reverend-{__version__}.dist-info/"
    )
    versioned = any(
        name.startswith(
            version_marker
        )
        for name
        in names
    )

    console_scripts = [
        name
        for name
        in names
        if name.endswith(
            ".dist-info/entry_points.txt"
        )
    ]

    if missing:
        raise ReleaseSmokeError(
            "Wheel is missing required release files: "
            + ", ".join(
                missing
            )
        )

    if not versioned:
        raise ReleaseSmokeError(
            "Wheel metadata version does not match the package version."
        )

    if len(
        console_scripts
    ) != 1:
        raise ReleaseSmokeError(
            "Wheel must contain one entry-points definition."
        )

    return {
        "files": len(
            names
        ),
        "required_files": sorted(
            _REQUIRED_WHEEL_PATHS
        ),
        "version_marker": (
            version_marker
        ),
        "entry_points": (
            console_scripts[0]
        ),
    }


def _venv_python(
    environment: Path,
) -> Path:
    return (
        environment
        / (
            "Scripts/python.exe"
            if os.name
            == "nt"
            else "bin/python"
        )
    )


def _venv_reverend(
    environment: Path,
) -> Path:
    return (
        environment
        / (
            "Scripts/reverend.exe"
            if os.name
            == "nt"
            else "bin/reverend"
        )
    )


def _installed_smoke(
    source: Path,
    wheel: Path,
    root: Path,
) -> dict:
    environment = (
        root
        / "venv"
    )

    venv.EnvBuilder(
        with_pip=True,
        system_site_packages=False,
        clear=True,
    ).create(
        environment
    )

    python = _venv_python(
        environment
    )
    reverend = _venv_reverend(
        environment
    )

    _run(
        [
            str(
                python
            ),
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            str(
                wheel
            ),
        ],
        cwd=source,
        timeout=120,
    )

    version = _run(
        [
            str(
                reverend
            ),
            "--version",
        ],
        cwd=root,
    ).stdout.strip()

    if version != (
        "reverend "
        + __version__
    ):
        raise ReleaseSmokeError(
            "Installed CLI version does not match the release version."
        )

    runtime_root = (
        root
        / "runtime"
    )
    config_root = (
        root
        / "config"
    )
    config_path = (
        config_root
        / "runtime.json"
    )
    key_path = (
        config_root
        / "state-v1.key"
    )
    qdrant_path = (
        runtime_root
        / "qdrant"
    )

    env = dict(
        os.environ
    )
    env.update(
        {
            "AI_DATA_ROOT": str(
                runtime_root
            ),
            "REVEREND_RUNTIME_CONFIG": str(
                config_path
            ),
            "REVEREND_STATE_KEY_FILE": str(
                key_path
            ),
            "QDRANT_PATH": str(
                qdrant_path
            ),
            "REVEREND_VAULT": str(
                root
                / "vault"
            ),
            "REVEREND_TEMPLATE": str(
                root
                / "vault"
                / "Master Note Template v20.md"
            ),
        }
    )

    script = r"""
import importlib.metadata
import json
import threading
import urllib.request
from pathlib import Path

import reverend
from reverend.workstation.server import LocalServer
from reverend.workstation.service import Workstation

expected = "0.4.0"
assert reverend.__version__ == expected
assert importlib.metadata.version("reverend") == expected

root = Path(__import__("os").environ["AI_DATA_ROOT"]).resolve()
service = Workstation(root)
server = LocalServer(("127.0.0.1", 0), service)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

try:
    port = server.server_port
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/",
        headers={"Host": f"127.0.0.1:{port}"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        body = response.read().decode("utf-8")
        assert response.status == 200

    assert "Reverend · Local engineering workstation" in body
    assert "Local inference" in body

    asset_request = urllib.request.Request(
        f"http://127.0.0.1:{port}/assets/app.js",
        headers={"Host": f"127.0.0.1:{port}"},
    )
    with urllib.request.urlopen(asset_request, timeout=5) as response:
        asset = response.read().decode("utf-8")
        assert response.status == 200

    assert "fetch(" in asset
    assert (root / "workstation.db").is_file()
    assert (root / "engineering-memory.db").is_file()
    assert (root / "public-sources.db").is_file()
    assert (root / "knowledge-cache-v1.db").is_file()

    print(json.dumps({
        "version": reverend.__version__,
        "port": port,
        "ui_ok": True,
        "runtime_root": str(root),
    }))
finally:
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()
    service.close()
"""

    completed = _run(
        [
            str(
                python
            ),
            "-c",
            script,
        ],
        cwd=root,
        env=env,
        timeout=60,
    )

    try:
        report = json.loads(
            completed.stdout.strip()
            .splitlines()[-1]
        )
    except (
        json.JSONDecodeError,
        IndexError,
    ) as exc:
        raise ReleaseSmokeError(
            "Installed Workstation smoke did not emit a valid report."
        ) from exc

    if not key_path.is_file():
        raise ReleaseSmokeError(
            "Release smoke did not create the isolated state key."
        )

    allowed_roots = {
        runtime_root.resolve(),
        config_root.resolve(),
        environment.resolve(),
    }

    for path in root.rglob(
        "*"
    ):
        if not path.is_file():
            continue

        resolved = (
            path.resolve()
        )

        if (
            path == wheel
            or resolved.is_relative_to(
                source.resolve()
            )
        ):
            continue

        if not any(
            resolved.is_relative_to(
                allowed
            )
            for allowed
            in allowed_roots
        ):
            raise ReleaseSmokeError(
                "Installed smoke wrote outside isolated release roots: "
                + str(
                    path
                )
            )

    return {
        **report,
        "cli_version": (
            version
        ),
        "key_created": True,
        "state_isolated": True,
    }


def run_release_smoke(
    repository: str | Path,
) -> dict:
    repository = Path(
        repository
    ).resolve()

    if not (
        repository
        / "pyproject.toml"
    ).is_file():
        raise ReleaseSmokeError(
            "Expected Reverend repository root."
        )

    with TemporaryDirectory(
        prefix="reverend-m15-release-"
    ) as temporary:
        root = Path(
            temporary
        )
        source = (
            root
            / "source"
        )
        (
            revision,
            tracked_changes,
        ) = _clean_head_archive(
            repository,
            source,
        )
        wheel = _build_wheel(
            source,
            root
            / "wheelhouse",
        )
        wheel_report = (
            _inspect_wheel(
                wheel
            )
        )
        installed = (
            _installed_smoke(
                source,
                wheel,
                root
                / "installed",
            )
        )

        return {
            "passed": True,
            "version": (
                __version__
            ),
            "revision": (
                revision
            ),
            "artifact_source": (
                "git archive HEAD"
            ),
            "tracked_worktree_changes": (
                tracked_changes
            ),
            "working_tree_changes_excluded": True,
            "wheel": (
                wheel.name
            ),
            "wheel_report": (
                wheel_report
            ),
            "installed": (
                installed
            ),
        }



def main(
    argv: list[str] | None = None,
) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "repository",
        nargs="?",
        default=".",
        type=Path,
    )
    args = parser.parse_args(
        argv
    )

    try:
        report = run_release_smoke(
            args.repository
        )
        code = 0
    except Exception as exc:
        report = {
            "passed": False,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }
        code = 1

    print(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    return code


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
