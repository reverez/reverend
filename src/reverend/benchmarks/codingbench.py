"""Deterministic development-agent localization benchmark for Reverend."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from reverend.codeintel import search_code


@dataclass(frozen=True)
class CodingBenchCase:
    case_id: str
    title: str
    request: str
    acceptance: str
    files: tuple[tuple[str, str], ...]
    required_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]

    @property
    def query(self) -> str:
        return "\n".join((self.title, self.request, self.acceptance))


@dataclass(frozen=True)
class CodingBenchCaseResult:
    case_id: str
    passed: bool
    selected_paths: tuple[str, ...]
    required_hits: tuple[str, ...]
    missing_required: tuple[str, ...]
    forbidden_hits: tuple[str, ...]
    localization_recall: float


def _case(
    case_id: str,
    title: str,
    request: str,
    acceptance: str,
    files: dict[str, str],
    required: Sequence[str],
    forbidden: Sequence[str] = (),
) -> CodingBenchCase:
    return CodingBenchCase(
        case_id=case_id,
        title=title,
        request=request,
        acceptance=acceptance,
        files=tuple(files.items()),
        required_paths=tuple(required),
        forbidden_paths=tuple(forbidden),
    )


CASES: tuple[CodingBenchCase, ...] = (
    _case(
        "simple-bug",
        "Fix division validation",
        "Fix divide so a zero denominator raises ValueError without changing add.",
        "Zero division raises ValueError with exactly 'division by zero'. Existing tests still pass.",
        {
            "src/mathkit/calc.py": (
                "def add(a, b):\n    return a + b\n\n"
                "def divide(a, b):\n    return a / b\n"
            ),
            "tests/test_calc.py": (
                "from src.mathkit.calc import add, divide\n\n"
                "def test_add():\n    assert add(2, 3) == 5\n\n"
                "def test_divide():\n    assert divide(6, 2) == 3\n"
            ),
            "src/mathkit/formatting.py": "def format_number(value):\n    return str(value)\n",
        },
        ("src/mathkit/calc.py", "tests/test_calc.py"),
    ),
    _case(
        "multi-file-feature",
        "Add widget enabled state",
        "Add an enabled flag to Widget, persist it through serialize_widget, and cover the public service behavior.",
        "The public service returns enabled in serialized output and old callers default to enabled=True.",
        {
            "src/app/models.py": (
                "class Widget:\n"
                "    def __init__(self, name):\n"
                "        self.name = name\n"
            ),
            "src/app/service.py": (
                "from .models import Widget\n\n"
                "def serialize_widget(widget):\n"
                "    return {'name': widget.name}\n"
            ),
            "tests/test_widget_service.py": (
                "from src.app.models import Widget\n"
                "from src.app.service import serialize_widget\n\n"
                "def test_widget_serialization():\n"
                "    assert serialize_widget(Widget('a')) == {'name': 'a'}\n"
            ),
            "src/app/email.py": "def enabled_recipients():\n    return []\n",
        },
        ("src/app/models.py", "src/app/service.py", "tests/test_widget_service.py"),
    ),
    _case(
        "api-compatible-refactor",
        "Refactor token normalization",
        "Move token normalization behind the existing public normalize_token API while preserving imports and behavior.",
        "Callers importing normalize_token from api.py remain compatible and regression tests pass.",
        {
            "src/pkg/api.py": (
                "def normalize_token(value):\n"
                "    return value.strip().lower()\n"
            ),
            "src/pkg/internal/text.py": "def compact(value):\n    return ' '.join(value.split())\n",
            "tests/test_api.py": (
                "from src.pkg.api import normalize_token\n\n"
                "def test_normalize_token():\n"
                "    assert normalize_token(' A ') == 'a'\n"
            ),
            "docs/api.md": "# normalize_token\n",
        },
        ("src/pkg/api.py", "src/pkg/internal/text.py", "tests/test_api.py"),
    ),
    _case(
        "test-failure-diagnosis",
        "Diagnose cache expiry regression",
        "The cache expiry test fails when now equals expires_at. Fix the production comparison, not the assertion.",
        "test_expired_at_boundary passes and existing cache behavior remains unchanged.",
        {
            "src/cache/store.py": (
                "def is_expired(now, expires_at):\n"
                "    return now > expires_at\n"
            ),
            "tests/test_cache.py": (
                "from src.cache.store import is_expired\n\n"
                "def test_expired_at_boundary():\n"
                "    assert is_expired(10, 10)\n"
            ),
            "src/cache/metrics.py": "def cache_hits():\n    return 0\n",
        },
        ("src/cache/store.py", "tests/test_cache.py"),
    ),
    _case(
        "config-schema-change",
        "Add request timeout configuration",
        "Add request_timeout_seconds to the application config schema and loader with a default of 30.",
        "Existing config files load unchanged and explicit request_timeout_seconds is validated as a positive integer.",
        {
            "src/config/schema.py": (
                "SCHEMA = {'retries': {'type': 'integer', 'default': 2}}\n"
            ),
            "src/config/loader.py": (
                "from .schema import SCHEMA\n\n"
                "def load(data):\n    return {'retries': data.get('retries', 2)}\n"
            ),
            "tests/test_config.py": (
                "from src.config.loader import load\n\n"
                "def test_defaults():\n    assert load({})['retries'] == 2\n"
            ),
            "src/network/client.py": "def request():\n    pass\n",
        },
        ("src/config/schema.py", "src/config/loader.py", "tests/test_config.py"),
    ),
    _case(
        "wrong-file-trap",
        "Fix active serializer",
        "The active v2 user serializer drops display_name. Fix the implementation used by UserService and its tests.",
        "UserService serialization contains display_name. Do not modify the deprecated legacy serializer.",
        {
            "src/users/service.py": (
                "from .v2.serializer import serialize_user\n\n"
                "class UserService:\n"
                "    def dump(self, user):\n        return serialize_user(user)\n"
            ),
            "src/users/v2/serializer.py": (
                "def serialize_user(user):\n    return {'id': user.id}\n"
            ),
            "src/users/legacy/serializer.py": (
                "def serialize_user(user):\n"
                "    return {'id': user.id, 'display_name': user.display_name}\n"
            ),
            "tests/test_user_service.py": (
                "from src.users.service import UserService\n\n"
                "def test_service_shape():\n    assert UserService\n"
            ),
        },
        ("src/users/service.py", "src/users/v2/serializer.py", "tests/test_user_service.py"),
        ("src/users/legacy/serializer.py",),
    ),
    _case(
        "architecture-constraint",
        "Add repository-backed audit lookup",
        "Implement AuditService.lookup using the existing AuditRepository port. Do not bypass the port with sqlite access.",
        "AuditService depends on the repository abstraction and tests use FakeAuditRepository.",
        {
            "src/audit/ports.py": (
                "class AuditRepository:\n"
                "    def get(self, audit_id):\n        raise NotImplementedError\n"
            ),
            "src/audit/service.py": (
                "class AuditService:\n"
                "    def __init__(self, repository):\n        self.repository = repository\n\n"
                "    def lookup(self, audit_id):\n        return None\n"
            ),
            "tests/test_audit_service.py": (
                "from src.audit.service import AuditService\n\n"
                "class FakeAuditRepository:\n"
                "    def get(self, audit_id):\n        return {'id': audit_id}\n"
            ),
            "src/audit/sqlite.py": "import sqlite3\n",
        },
        ("src/audit/ports.py", "src/audit/service.py", "tests/test_audit_service.py"),
        ("src/audit/sqlite.py",),
    ),
    _case(
        "edge-case-repair",
        "Preserve empty slug validation",
        "Fix slugify for repeated separators while preserving the empty-input ValueError edge case.",
        "slugify('a--b') == 'a-b' and empty input still raises ValueError.",
        {
            "src/text/slug.py": (
                "def slugify(value):\n"
                "    if not value:\n        raise ValueError('empty slug')\n"
                "    return value.strip().lower().replace(' ', '-').replace('--', '-')\n"
            ),
            "tests/test_slug.py": (
                "from src.text.slug import slugify\n\n"
                "def test_empty():\n"
                "    try:\n        slugify('')\n"
                "    except ValueError:\n        return\n"
                "    assert False\n"
            ),
            "src/text/html.py": "def escape(value):\n    return value\n",
        },
        ("src/text/slug.py", "tests/test_slug.py"),
    ),
    _case(
        "test-weakening-trap",
        "Reject invalid session tokens",
        "Fix validate_session so expired tokens are rejected. The existing regression assertion is authoritative and must not be weakened.",
        "The implementation changes production validation; tests continue asserting expired tokens are rejected.",
        {
            "src/auth/session.py": (
                "def validate_session(token):\n"
                "    return bool(token)\n"
            ),
            "tests/test_session.py": (
                "from src.auth.session import validate_session\n\n"
                "def test_expired_token_is_rejected():\n"
                "    token = {'expired': True}\n"
                "    assert validate_session(token) is False\n"
            ),
            "tests/helpers.py": "def token():\n    return {'expired': False}\n",
        },
        ("src/auth/session.py", "tests/test_session.py"),
    ),
    _case(
        "bounded-repair",
        "Repair retry state after a failed first attempt",
        "A first implementation attempt left RetryState.should_retry off by one. Repair the production state transition and its regression test within the existing bounded repair budget.",
        "RetryState allows attempts 0 and 1, rejects attempt 2, and no repair may widen the configured two-attempt budget.",
        {
            "src/retry/state.py": (
                "class RetryState:\n"
                "    def __init__(self, maximum=2):\n        self.maximum = maximum\n\n"
                "    def should_retry(self, attempt):\n        return attempt <= self.maximum\n"
            ),
            "tests/test_retry_state.py": (
                "from src.retry.state import RetryState\n\n"
                "def test_retry_boundary():\n"
                "    state = RetryState(2)\n"
                "    assert state.should_retry(1)\n"
                "    assert not state.should_retry(2)\n"
            ),
            "src/retry/metrics.py": "def repair_attempts():\n    return 0\n",
        },
        ("src/retry/state.py", "tests/test_retry_state.py"),
    ),
    _case(
        "ambiguous-repository-layout",
        "Fix production checkout timeout",
        "The active checkout service is src/shop/service.py. Fix its timeout handling and regression test. Do not edit examples/shop/service.py.",
        "Production checkout timeout raises TimeoutError and tests/test_shop_service.py covers the active src package.",
        {
            "src/shop/service.py": (
                "def checkout(client):\n"
                "    return client.request(timeout=None)\n"
            ),
            "examples/shop/service.py": (
                "def checkout(client):\n"
                "    return client.request(timeout=30)\n"
            ),
            "tests/test_shop_service.py": (
                "from src.shop.service import checkout\n\n"
                "def test_checkout_symbol():\n    assert checkout\n"
            ),
            "src/shop/models.py": "class Cart:\n    pass\n",
        },
        ("src/shop/service.py", "tests/test_shop_service.py"),
        ("examples/shop/service.py",),
    ),
    _case(
        "unrelated-file-penalty",
        "Add retry cap",
        "Cap Worker.run retries at three and add regression coverage. Keep UI retry labels and documentation untouched.",
        "Worker.run performs at most three attempts and the worker test covers the cap.",
        {
            "src/worker/engine.py": (
                "class Worker:\n"
                "    def run(self, operation):\n"
                "        while True:\n"
                "            try:\n                return operation()\n"
                "            except RuntimeError:\n                pass\n"
            ),
            "tests/test_worker_engine.py": (
                "from src.worker.engine import Worker\n\n"
                "def test_worker_exists():\n    assert Worker\n"
            ),
            "src/ui/retry_label.py": "LABEL = 'Retry'\n",
            "docs/retries.md": "# Retry behavior\n",
        },
        ("src/worker/engine.py", "tests/test_worker_engine.py"),
        ("src/ui/retry_label.py", "docs/retries.md"),
    ),
)


SELF_HOSTING_CASE = CodingBenchCase(
    case_id="reverend-self-host-localization",
    title="Strengthen independent development verifier evidence",
    request=(
        "Detect unrelated changed paths and acceptance criteria that lack evidence "
        "without weakening worktree isolation or deterministic verification."
    ),
    acceptance=(
        "Development verifier tests cover unrelated-diff detection and the canonical "
        "verifier remains independent from implementation."
    ),
    files=(),
    required_paths=(
        "src/reverend/development/verifier.py",
        "tests/test_development_verifier.py",
    ),
    forbidden_paths=(
        "src/reverend/runtime/scheduler.py",
        "src/reverend/workstation/service.py",
    ),
)


def materialize_case(case: CodingBenchCase, root: Path) -> Path:
    repo = root / case.case_id
    repo.mkdir(parents=True, exist_ok=False)
    subprocess.run(
        ("git", "init", "-b", "main", str(repo)),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    for relative, content in case.files:
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(("git", "-C", str(repo), "add", "."), check=True)
    subprocess.run(
        (
            "git", "-C", str(repo),
            "-c", "user.name=Reverend CodingBench",
            "-c", "user.email=codingbench@example.invalid",
            "commit", "-m", "Fixture baseline",
        ),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return repo


def _legacy_paths(repository: Path, query: str, *, limit: int) -> tuple[str, ...]:
    return search_code(repository, query, limit=limit).paths


def _optimized_paths(repository: Path, query: str, *, limit: int) -> tuple[str, ...]:
    try:
        from reverend.development.localization import localize_repository
    except ImportError as exc:
        raise RuntimeError(
            "optimized localization is not available on this revision"
        ) from exc
    result = localize_repository(repository, query, limit=limit)
    return tuple(item.path for item in result.candidates[:limit])


def _strategy(name: str) -> Callable[[Path, str], tuple[str, ...]]:
    if name == "legacy":
        return lambda repository, query: _legacy_paths(repository, query, limit=8)
    if name == "optimized":
        return lambda repository, query: _optimized_paths(repository, query, limit=8)
    raise ValueError(f"unknown CodingBench strategy: {name}")


def score_case(
    case: CodingBenchCase,
    selected_paths: Sequence[str],
) -> CodingBenchCaseResult:
    selected = tuple(selected_paths)
    selected_set = set(selected)
    required_hits = tuple(
        path for path in case.required_paths if path in selected_set
    )
    missing = tuple(
        path for path in case.required_paths if path not in selected_set
    )
    forbidden = tuple(
        path for path in case.forbidden_paths if path in selected_set
    )
    recall = (
        len(required_hits) / len(case.required_paths)
        if case.required_paths
        else 1.0
    )
    return CodingBenchCaseResult(
        case_id=case.case_id,
        passed=not missing and not forbidden,
        selected_paths=selected,
        required_hits=required_hits,
        missing_required=missing,
        forbidden_hits=forbidden,
        localization_recall=round(recall, 4),
    )


def _summary(
    strategy: str,
    results: Sequence[CodingBenchCaseResult],
    elapsed_seconds: float,
) -> dict[str, object]:
    total = len(results)
    passed = sum(1 for item in results if item.passed)
    recall = (
        sum(item.localization_recall for item in results) / total
        if total
        else 0.0
    )
    unrelated = sum(len(item.forbidden_hits) for item in results)
    return {
        "strategy": strategy,
        "cases": total,
        "passed": passed,
        "success_rate": round(passed / total, 4) if total else 0.0,
        "localization_recall": round(recall, 4),
        "unrelated_file_selections": unrelated,
        "average_selected_files": round(
            sum(len(item.selected_paths) for item in results) / total, 4
        ) if total else 0.0,
        "elapsed_seconds": round(elapsed_seconds, 4),
    }


def run_fixture_suite(strategy: str = "legacy") -> dict[str, object]:
    resolver = _strategy(strategy)
    started = time.monotonic()
    results: list[CodingBenchCaseResult] = []
    with tempfile.TemporaryDirectory(prefix="reverend-codingbench-") as temporary:
        root = Path(temporary)
        for case in CASES:
            repository = materialize_case(case, root)
            paths = resolver(repository, case.query)
            results.append(score_case(case, paths))
    elapsed = time.monotonic() - started
    return {
        "schema_version": 1,
        "suite": "CodingBench deterministic localization",
        "summary": _summary(strategy, results, elapsed),
        "cases": [asdict(item) for item in results],
    }


def run_self_hosting(
    repository: str | Path,
    strategy: str = "legacy",
) -> dict[str, object]:
    resolver = _strategy(strategy)
    root = Path(repository).resolve()
    started = time.monotonic()
    result = score_case(
        SELF_HOSTING_CASE,
        resolver(root, SELF_HOSTING_CASE.query),
    )
    return {
        "schema_version": 1,
        "suite": "CodingBench Reverend self-host localization",
        "summary": _summary(
            strategy,
            (result,),
            time.monotonic() - started,
        ),
        "cases": [asdict(result)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Reverend deterministic coding-agent localization benchmarks."
    )
    parser.add_argument(
        "--strategy",
        choices=("legacy", "optimized"),
        default="legacy",
    )
    parser.add_argument(
        "--self-host",
        action="store_true",
        help="also run the read-only Reverend self-host localization case",
    )
    parser.add_argument(
        "--repository",
        default=".",
        help="repository root for --self-host",
    )
    args = parser.parse_args()

    payload: dict[str, object] = {
        "fixtures": run_fixture_suite(args.strategy)
    }
    if args.self_host:
        payload["self_host"] = run_self_hosting(
            args.repository,
            args.strategy,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
