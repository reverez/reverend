from __future__ import annotations

import json

from reverend.benchmarks.command import (
    command_benchmark_list,
    command_benchmark_run_unavailable,
)
from reverend.benchmarks.models import (
    BenchmarkCase,
    BenchmarkCategory,
)


def test_benchmark_list_emits_machine_readable_catalogue(
    capsys,
):
    cases = (
        BenchmarkCase(
            case_id="entity-xavier",
            name="Resolve Xavier entity",
            category=BenchmarkCategory.OPEN_DOMAIN,
            prompt="xaiver the renegade angel",
            tags=("entity", "reference"),
        ),
    )

    result = command_benchmark_list(cases)

    assert result == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["count"] == 1
    assert payload["cases"][0]["case_id"] == "entity-xavier"
    assert payload["cases"][0]["category"] == "open_domain"
    assert payload["cases"][0]["tags"] == [
        "entity",
        "reference",
    ]


def test_unavailable_run_fails_explicitly(
    capsys,
):
    result = command_benchmark_run_unavailable()

    assert result == 2

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["ok"] is False
    assert "M6.3" in payload["error"]


def test_benchmark_run_isolates_state_but_uses_canonical_knowledge(
    tmp_path,
    capsys,
):
    from pathlib import Path

    from reverend.benchmarks.command import command_benchmark_run
    from reverend.benchmarks.models import (
        BenchmarkCase,
        BenchmarkCategory,
        BenchmarkObservation,
    )

    captured = {}

    class FakeWorkstation:
        def __init__(
            self,
            *,
            root,
            knowledge_db_path,
        ):
            captured["root"] = Path(root)
            captured["knowledge_db_path"] = Path(
                knowledge_db_path
            )
            self.closed = False

        def close(self):
            self.closed = True
            captured["closed"] = True

    def executor_factory(_workstation):
        return lambda _case: BenchmarkObservation(
            response="valid benchmark response",
            metadata={},
        )

    cases = (
        BenchmarkCase(
            case_id="isolation-case",
            name="Isolation case",
            category=BenchmarkCategory.RESEARCH,
            prompt="test",
        ),
    )

    result = command_benchmark_run(
        cases,
        data_root=tmp_path,
        workstation_factory=FakeWorkstation,
        executor_factory=executor_factory,
    )

    assert result == 0
    assert captured["root"] != tmp_path
    assert captured["knowledge_db_path"] == (
        tmp_path / "platform.db"
    )
    assert captured["closed"] is True

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["metadata"]["state_isolated"] is True
    assert payload["summary"]["passed"] == 1

    report = Path(payload["report_path"])

    assert report.exists()
    assert report.is_relative_to(
        tmp_path / "benchmarks" / "runs"
    )


def test_timed_out_worker_finishes_before_isolated_state_is_removed(tmp_path,capsys):
    import threading
    from reverend.workstation.service import Workstation
    from reverend.benchmarks.command import command_benchmark_run
    from reverend.benchmarks.models import BenchmarkBudget
    from reverend.benchmarks.workstation import WorkstationChatExecutor

    entered=threading.Event()
    completed=threading.Event()
    roots=[]

    class Scheduler:
        def stream(self,role,prompt,cancel=None):
            entered.set()
            cancel.wait(2)
            assert roots[0].exists()
            completed.set()
            return
            yield

    class ControlledClock:
        def __init__(self):
            self.first=True

        def __call__(self):
            if self.first:
                self.first=False
                return 0.0
            return 1.0 if entered.is_set() else 0.0

    def factory(**kwargs):
        roots.append(kwargs['root'])
        return Workstation(**kwargs,scheduler_factory=Scheduler)

    clock=ControlledClock()
    case=BenchmarkCase(
        case_id='cancel',
        name='Cancel',
        category=BenchmarkCategory.RESEARCH,
        prompt='hello',
        budget=BenchmarkBudget(timeout_seconds=.02),
    )

    code=command_benchmark_run(
        [case],
        data_root=tmp_path,
        workstation_factory=factory,
        executor_factory=lambda app:WorkstationChatExecutor(
            app,
            poll_interval=.001,
            clock=clock,
            sleep=lambda _: entered.wait(1),
        ),
    )

    assert code==1 and completed.is_set()
    assert not roots[0].exists()
    assert json.loads(capsys.readouterr().out)['summary']['timeouts']==1
