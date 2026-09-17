from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Incident:
    created_at: str
    severity: str
    kind: str
    message: str
    session_id: str | None = None
    issue_number: int | None = None
    details: dict[str, Any] | None = None


class IncidentReporter:
    """Durably record autonomy incidents and optionally fan them out.

    The local JSONL journal is authoritative. External delivery is best-effort and
    never changes controller outcome. Configure REVEREND_ALERT_COMMAND to execute a
    local notifier with the incident JSON on stdin, or REVEREND_ALERT_WEBHOOK_URL
    to POST the same JSON to an external endpoint. When no explicit destination is
    configured, WARNING/CRITICAL incidents use notify-send when available.
    """

    def __init__(self, repository_root: str | Path) -> None:
        self.root = Path(repository_root).resolve()
        self.runtime = self.root / ".autonomy" / "v2-production"
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.path = self.runtime / "incidents.jsonl"

    def emit(
        self,
        *,
        severity: str,
        kind: str,
        message: str,
        session_id: str | None = None,
        issue_number: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> Incident:
        incident = Incident(
            created_at=datetime.now(UTC).isoformat(),
            severity=severity.upper(),
            kind=kind,
            message=message,
            session_id=session_id,
            issue_number=issue_number,
            details=details or {},
        )
        payload = json.dumps(asdict(incident), sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")
            handle.flush()
            os.fsync(handle.fileno())

        configured = bool(
            os.environ.get("REVEREND_ALERT_COMMAND", "").strip()
            or os.environ.get("REVEREND_ALERT_WEBHOOK_URL", "").strip()
        )
        self._command(payload)
        self._webhook(payload)
        if not configured and incident.severity in {"WARNING", "CRITICAL"}:
            self._desktop(incident)
        return incident

    def latest(self, limit: int = 20) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be positive")
        if not self.path.is_file():
            return []
        lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        result: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                result.append(value)
        return result

    @staticmethod
    def _command(payload: str) -> None:
        raw = os.environ.get("REVEREND_ALERT_COMMAND", "").strip()
        if not raw:
            return
        try:
            argv = shlex.split(raw)
            if not argv:
                return
            subprocess.run(
                argv,
                input=payload + "\n",
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return

    @staticmethod
    def _webhook(payload: str) -> None:
        url = os.environ.get("REVEREND_ALERT_WEBHOOK_URL", "").strip()
        if not url:
            return
        request = urllib.request.Request(
            url,
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                response.read(1)
        except Exception:
            # Alert delivery must never be able to crash autonomous development.
            return

    @staticmethod
    def _desktop(incident: Incident) -> None:
        executable = shutil.which("notify-send")
        if not executable:
            return
        title = f"Reverend {incident.severity}: {incident.kind}"
        body = incident.message
        if incident.issue_number is not None:
            body = f"Issue #{incident.issue_number}: {body}"
        try:
            subprocess.run(
                [executable, title, body],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return
