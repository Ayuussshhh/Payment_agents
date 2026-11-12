"""Approval snapshots. A signature is stored, and the database row wins."""

from mandate_core.approval.engine import ApprovalEngine
from mandate_core.approval.signature import sign_snapshot, token_matches

__all__ = ["ApprovalEngine", "sign_snapshot", "token_matches"]
