from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Iterable

from .controller import IssueSpec

_MILESTONE_RE = re.compile(
    r"^\*\*Milestone:\*\*\s*C(?P<number>[0-9]+)\s+[—-]\s+(?P<name>.+?)\s*$",
    re.MULTILINE,
)
_OWNER_RE = re.compile(r"^\*\*Owner:\*\*\s*(?P<owner>[^\s]+)\s*$", re.MULTILINE)
_AREA_RE = re.compile(r"^\*\*Area:\*\*\s*(?P<area>.+?)\s*$", re.MULTILINE)


class QueueLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class QueuedIssue:
    number: int
    title: str
    body: str
    owner: str
    milestone_number: int
    milestone_name: str
    area: str

    @property
    def milestone(self) -> str:
        return f"C{self.milestone_number}"

    def as_issue_spec(self) -> IssueSpec:
        return IssueSpec(
            number=self.number,
            milestone=self.milestone,
            title=self.title,
        )


class GitHubIssueQueue:
    """Load the canonical C0-C9 queue through the authenticated gh CLI."""

    def __init__(
        self,
        repository: str,
        *,
        gh_executable: str = "gh",
        allowed_owners: Iterable[str] = ("arnav", "shared"),
        include_alex: bool = False,
    ) -> None:
        self.repository = repository
        self.gh_executable = gh_executable
        owners = {owner.strip().lower() for owner in allowed_owners}
        if include_alex:
            owners.add("alex")
        self.allowed_owners = frozenset(owners)

    def load(self) -> tuple[QueuedIssue, ...]:
        try:
            completed = subprocess.run(
                [
                    self.gh_executable,
                    "issue",
                    "list",
                    "--repo",
                    self.repository,
                    "--state",
                    "open",
                    "--limit",
                    "300",
                    "--json",
                    "number,title,body,state",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise QueueLoadError(f"unable to query GitHub issues: {exc}") from exc
        if completed.returncode != 0:
            raise QueueLoadError(
                "gh issue list failed: " + completed.stderr.strip()[-2000:]
            )
        try:
            raw = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise QueueLoadError(f"gh returned invalid JSON: {exc}") from exc
        if not isinstance(raw, list):
            raise QueueLoadError("gh issue list did not return a JSON list")

        issues: list[QueuedIssue] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            body = str(item.get("body") or "")
            milestone_match = _MILESTONE_RE.search(body)
            owner_match = _OWNER_RE.search(body)
            if milestone_match is None or owner_match is None:
                continue
            milestone_number = int(milestone_match.group("number"))
            if not 0 <= milestone_number <= 9:
                continue
            owner = owner_match.group("owner").strip().lower()
            if owner not in self.allowed_owners:
                continue
            area_match = _AREA_RE.search(body)
            issues.append(
                QueuedIssue(
                    number=int(item["number"]),
                    title=str(item["title"]),
                    body=body,
                    owner=owner,
                    milestone_number=milestone_number,
                    milestone_name=milestone_match.group("name").strip(),
                    area=area_match.group("area").strip() if area_match else "unknown",
                )
            )

        issues.sort(key=lambda issue: (issue.milestone_number, issue.number))
        if not issues:
            raise QueueLoadError("no eligible C0-C9 issues were discovered")
        return tuple(issues)
