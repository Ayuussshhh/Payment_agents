"""Catalog check. The permission tuple is already expanded for this membership."""

from mandate_core.contracts import ExecutionContext
from mandate_core.errors import EngineError


def authorize_action(context: ExecutionContext, action: str, subject: str) -> None:
    grant = f"{action}:{subject}"
    if grant not in context.permissions:
        raise EngineError("forbidden", "That action is not allowed.", 403)
