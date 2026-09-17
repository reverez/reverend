"""Durable controller primitives for Reverend autonomous development v2.

The v2 controller deliberately keeps workflow state outside the language model.
LLMs may plan, edit, and review, but deterministic code owns transitions,
verification, recovery, and acceptance.
"""

from .context import ContextBuilder, IssuePacket
from .gitops import GitCommandError, WorktreeManager
from .state import IssuePhase, StateStore, TransitionError

__all__ = [
    "ContextBuilder",
    "GitCommandError",
    "IssuePacket",
    "IssuePhase",
    "StateStore",
    "TransitionError",
    "WorktreeManager",
]
