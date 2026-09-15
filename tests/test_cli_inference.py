from __future__ import annotations

from reverend.cli import command_chat


class FakeStore:
    def __init__(self, job):
        self._job = job

    def job(self, identity):
        assert identity == "job-1"
        return self._job


class FakeWorkstation:
    def __init__(self, job):
        self.store = FakeStore(job)
        self.calls = []
        self.closed = False

    def chat(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return {
            "job_id": "job-1",
            "conversation_id": "conversation-1",
        }

    def close(self):
        self.closed = True


def test_cli_ask_uses_ephemeral_canonical_workstation(
    monkeypatch,
    capsys,
):
    app = FakeWorkstation(
        {
            "status": "complete",
            "response": "canonical answer",
            "details": {
                "model": "local-model",
            },
        }
    )
    events = []
    monkeypatch.setattr(
        "reverend.cli.log_event",
        lambda *args, **kwargs: events.append(
            (args, kwargs)
        ),
    )

    result = command_chat(
        "hello",
        "ask",
        workstation_factory=lambda root: app,
    )

    assert result == 0
    assert capsys.readouterr().out.strip() == (
        "canonical answer"
    )
    assert app.calls == [
        (
            "hello",
            {
                "mode": "ask",
                "network_policy": "OFF",
                "privacy_mode": "ephemeral",
            },
        )
    ]
    assert app.closed is True
    assert events


def test_cli_reason_preserves_context_error_code(
    monkeypatch,
    capsys,
):
    app = FakeWorkstation(
        {
            "status": "failed",
            "response": "",
            "details": {
                "error_code": "context_budget_exceeded",
                "error": "Request exceeds safe context budget.",
                "role": "deep_reason",
            },
        }
    )
    monkeypatch.setattr(
        "reverend.cli.log_event",
        lambda *args, **kwargs: None,
    )

    result = command_chat(
        "oversized",
        "reason",
        workstation_factory=lambda root: app,
    )

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert (
        "context_budget_exceeded"
        in captured.err
    )
    assert app.calls[0][1]["mode"] == "reason"
    assert app.closed is True
