"""One approval binds one cart. A changed line kills that approval."""

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.approval.signature import sign_snapshot, stamp, token_matches
from mandate_core.commerce.carts import current_hash
from mandate_core.contracts import Approval, EventEnvelope, ExecutionContext
from mandate_core.errors import EngineError
from mandate_core.events import append_event
from mandate_core.identity import authorize_action
from mandate_core.persistence.scope import use_tenant_scope

_INSERT = text(
    """
    insert into approvals.approvals (
      id, organization_id, proposal_id, policy_version_id, agent_version_id, approver_user_id,
      cart_hash, hash_version, amount_minor, currency, merchant_id, status, snapshot, signature, expires_at
    )
    values (
      :id, :organization_id, :proposal_id, :policy_version_id, :agent_version_id, :approver_user_id,
      :cart_hash, :hash_version, :amount_minor, :currency, :merchant_id, :status,
      cast(:snapshot as jsonb), :signature, :expires_at
    )
    """
)

_BY_ID = text(
    """
    select a.id, a.organization_id, a.proposal_id, a.policy_version_id, a.agent_version_id,
           a.approver_user_id, a.cart_hash, a.hash_version, a.amount_minor, a.currency, a.merchant_id,
           a.status, a.signature, a.expires_at, a.created_at, v.version as policy_version, v.expires_at as policy_expires_at
    from approvals.approvals a
    join policies.policy_versions v on v.id = a.policy_version_id
    where a.organization_id = :organization_id and a.id = :approval_id
    """
)

_LOCK = text(
    """
    select id from approvals.approvals
    where organization_id = :organization_id and id = :approval_id
    for update
    """
)

_BY_PROPOSAL = text(
    """
    select id from approvals.approvals
    where organization_id = :organization_id and proposal_id = :proposal_id
    """
)

_LIST = text(
    """
    select id from approvals.approvals
    where organization_id = :organization_id
    order by created_at desc
    limit 200
    """
)

_EVALUATION = text(
    """
    select decision, cart_hash, policy_version_id
    from policies.evaluations
    where organization_id = :organization_id and proposal_id = :proposal_id
    order by created_at desc
    limit 1
    """
)

_POLICY = text(
    """
    select status, version, expires_at
    from policies.policy_versions
    where organization_id = :organization_id and id = :version_id
    """
)

_KEY = text(
    """
    select resource_id, request_hash
    from approvals.idempotency_keys
    where organization_id = :organization_id and scope = :scope and key = :key
    """
)

_INSERT_KEY = text(
    """
    insert into approvals.idempotency_keys (organization_id, scope, key, request_hash, resource_id)
    values (:organization_id, :scope, :key, :request_hash, :resource_id)
    """
)

_STATUS = text(
    """
    update approvals.approvals
    set status = :status
    where organization_id = :organization_id and id = :approval_id
    """
)

_GRANT = text(
    """
    update approvals.approvals
    set status = 'valid', approver_user_id = :approver_user_id, signature = :signature, snapshot = cast(:snapshot as jsonb)
    where organization_id = :organization_id and id = :approval_id and status = 'pending'
    """
)


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _require_user(context: ExecutionContext) -> None:
    if context.user_id is None:
        raise EngineError("unauthenticated", "A user is required.", 401)


def _require_key(idempotency_key: str) -> None:
    if not idempotency_key:
        raise EngineError("idempotency_key_required", "An Idempotency-Key header is required.", 400)


def _hash(scope: str, resource: str) -> str:
    return hashlib.sha256(f"{scope}:{resource}".encode()).hexdigest()


def _event(context: ExecutionContext, name: str, approval_id: UUID, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        id=uuid4(),
        organization_id=context.organization_id,
        name=name,
        aggregate_type="approval",
        aggregate_id=approval_id,
        actor_type="user",
        actor_id=str(context.user_id),
        request_id=context.request_id,
        payload=payload,
        occurred_at=datetime.now(timezone.utc),
    )


def _approval(row) -> Approval:
    approver = row["approver_user_id"]
    agent_version = row["agent_version_id"]
    return Approval(
        id=row["id"],
        organization_id=row["organization_id"],
        proposal_id=row["proposal_id"],
        policy_version_id=row["policy_version_id"],
        policy_version=row["policy_version"],
        agent_version_id=None if agent_version is None else agent_version,
        approver_user_id=None if approver is None else UUID(str(approver)),
        cart_hash=row["cart_hash"],
        hash_version=row["hash_version"],
        amount_minor=row["amount_minor"],
        currency=str(row["currency"]).strip(),
        merchant_id=row["merchant_id"],
        status=row["status"],
        expires_at=row["expires_at"],
        created_at=row["created_at"],
        signature=row["signature"],
    )


class ApprovalEngine:
    def request_approval(
        self,
        connection: Connection,
        context: ExecutionContext,
        proposal_id: UUID,
        idempotency_key: str,
        now: datetime | None = None,
        signing_key: bytes | None = None,
    ) -> Approval:
        del signing_key
        _require_user(context)
        authorize_action(context, "create", "Approval")
        _require_key(idempotency_key)
        current = _aware(now)
        use_tenant_scope(connection, context.organization_id)
        request_hash = _hash("request", str(proposal_id))
        replay = self._replay(connection, context, "request", idempotency_key, request_hash, current)
        if replay is not None:
            return replay
        existing_id = connection.execute(
            _BY_PROPOSAL,
            {"organization_id": context.organization_id, "proposal_id": proposal_id},
        ).scalar()
        if existing_id is not None:
            self._remember(connection, context, "request", idempotency_key, request_hash, existing_id)
            return self._prepare(connection, context, existing_id, current)
        _proposal, meta, digest = current_hash(connection, context.organization_id, proposal_id)
        evaluation = connection.execute(
            _EVALUATION,
            {"organization_id": context.organization_id, "proposal_id": proposal_id},
        ).mappings().first()
        if evaluation is None or evaluation["decision"] != "needs_approval" or not evaluation["cart_hash"]:
            raise EngineError("not_found", "That proposal is not waiting for approval.", 404)
        if meta["policy_status"] != "active":
            raise EngineError("mandate_inactive", "That policy version is not active.", 400)
        if digest != meta["stored_hash"] or digest != evaluation["cart_hash"]:
            raise EngineError("intent_mismatch", "The cart no longer matches the evaluated proposal.", 409)
        policy = connection.execute(
            _POLICY,
            {"organization_id": context.organization_id, "version_id": meta["policy_version_id"]},
        ).mappings().one()
        expires_at = policy["expires_at"]
        if current >= _aware(expires_at):
            raise EngineError("mandate_expired", "That policy version has expired.", 400)
        approval_id = uuid4()
        amount = _proposal.total_minor
        connection.execute(
            _INSERT,
            {
                "id": approval_id,
                "organization_id": context.organization_id,
                "proposal_id": proposal_id,
                "policy_version_id": meta["policy_version_id"],
                "agent_version_id": context.agent_version_id,
                "approver_user_id": None,
                "cart_hash": digest,
                "hash_version": meta["hash_version"],
                "amount_minor": amount,
                "currency": _proposal.currency,
                "merchant_id": meta["seller_id"],
                "status": "pending",
                "snapshot": "{}",
                "signature": None,
                "expires_at": expires_at,
            },
        )
        self._remember(connection, context, "request", idempotency_key, request_hash, approval_id)
        append_event(
            connection,
            context,
            _event(context, "approval.requested", approval_id, {"approval_id": str(approval_id), "proposal_id": str(proposal_id)}),
        )
        return self._load(connection, context, approval_id)

    def approve(
        self,
        connection: Connection,
        context: ExecutionContext,
        approval_id: UUID,
        idempotency_key: str,
        now: datetime | None = None,
        signing_key: bytes | None = None,
    ) -> Approval:
        _require_user(context)
        authorize_action(context, "approve", "Approval")
        _require_key(idempotency_key)
        current = _aware(now)
        use_tenant_scope(connection, context.organization_id)
        request_hash = _hash("approve", str(approval_id))
        replay = self._replay(connection, context, "approve", idempotency_key, request_hash, current)
        if replay is not None:
            return replay
        self._lock(connection, context, approval_id)
        approval = self._prepare(connection, context, approval_id, current)
        if approval.status == "expired":
            raise EngineError("approval_expired", "That approval has expired.", 409)
        if approval.status != "pending":
            raise EngineError("approval_replayed", "That approval is not pending.", 409)
        _proposal, meta, digest = current_hash(connection, context.organization_id, approval.proposal_id)
        if digest != approval.cart_hash or digest != meta["stored_hash"] or meta["policy_status"] != "active":
            if digest != approval.cart_hash or digest != meta["stored_hash"]:
                raise EngineError("intent_mismatch", "The cart no longer matches the approval snapshot.", 409)
            raise EngineError("mandate_inactive", "That policy version is not active.", 400)
        fields = {
            "organization_id": approval.organization_id,
            "approver_user_id": context.user_id,
            "agent_version_id": approval.agent_version_id,
            "policy_version_id": approval.policy_version_id,
            "policy_version": approval.policy_version,
            "proposal_id": approval.proposal_id,
            "cart_hash": approval.cart_hash,
            "hash_version": approval.hash_version,
            "amount_minor": approval.amount_minor,
            "currency": approval.currency,
            "merchant_id": approval.merchant_id,
            "expires_at": stamp(approval.expires_at),
        }
        signature = sign_snapshot(fields, signing_key)
        connection.execute(
            _GRANT,
            {
                "organization_id": context.organization_id,
                "approval_id": approval_id,
                "approver_user_id": str(context.user_id),
                "signature": signature,
                "snapshot": json.dumps(fields, default=str),
            },
        )
        self._remember(connection, context, "approve", idempotency_key, request_hash, approval_id)
        append_event(
            connection,
            context,
            _event(context, "approval.granted", approval_id, {"approval_id": str(approval_id), "proposal_id": str(approval.proposal_id)}),
        )
        return self._load(connection, context, approval_id)

    def reject(
        self,
        connection: Connection,
        context: ExecutionContext,
        approval_id: UUID,
        reason: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> Approval:
        _require_user(context)
        authorize_action(context, "reject", "Approval")
        _require_key(idempotency_key)
        current = _aware(now)
        use_tenant_scope(connection, context.organization_id)
        request_hash = _hash("reject", f"{approval_id}:{reason}")
        replay = self._replay(connection, context, "reject", idempotency_key, request_hash, current)
        if replay is not None:
            return replay
        self._lock(connection, context, approval_id)
        approval = self._prepare(connection, context, approval_id, current)
        if approval.status == "expired":
            raise EngineError("approval_expired", "That approval has expired.", 409)
        if approval.status == "pending":
            target = "rejected"
            event_name = "approval.rejected"
        elif approval.status == "valid":
            target = "revoked"
            event_name = "approval.revoked"
        else:
            raise EngineError("approval_replayed", "That approval can no longer be rejected.", 409)
        connection.execute(
            _STATUS,
            {"status": target, "organization_id": context.organization_id, "approval_id": approval_id},
        )
        self._remember(connection, context, "reject", idempotency_key, request_hash, approval_id)
        append_event(
            connection,
            context,
            _event(context, event_name, approval_id, {"approval_id": str(approval_id), "reason": reason}),
        )
        return self._load(connection, context, approval_id)

    def expire(self, connection: Connection, context: ExecutionContext, now: datetime | None = None) -> int:
        _require_user(context)
        authorize_action(context, "reject", "Approval")
        current = _aware(now)
        use_tenant_scope(connection, context.organization_id)
        identifiers = connection.execute(_LIST, {"organization_id": context.organization_id}).scalars().all()
        count = 0
        for approval_id in identifiers:
            current_row = self._load(connection, context, approval_id)
            due = current_row.status in {"pending", "valid"} and current >= _aware(current_row.expires_at)
            self._prepare(connection, context, approval_id, current)
            if due:
                count += 1
        return count

    def get(self, connection: Connection, context: ExecutionContext, approval_id: UUID, now: datetime | None = None) -> Approval:
        _require_user(context)
        authorize_action(context, "read", "Approval")
        use_tenant_scope(connection, context.organization_id)
        return self._prepare(connection, context, approval_id, _aware(now))

    def list_approvals(self, connection: Connection, context: ExecutionContext, now: datetime | None = None) -> list[Approval]:
        _require_user(context)
        authorize_action(context, "read", "Approval")
        current = _aware(now)
        use_tenant_scope(connection, context.organization_id)
        identifiers = connection.execute(_LIST, {"organization_id": context.organization_id}).scalars().all()
        return [self._prepare(connection, context, approval_id, current) for approval_id in identifiers]

    def signature_authorizes(
        self,
        connection: Connection,
        context: ExecutionContext,
        approval_id: UUID,
        token: str,
        now: datetime | None = None,
        signing_key: bytes | None = None,
    ) -> bool:
        _require_user(context)
        authorize_action(context, "read", "Approval")
        use_tenant_scope(connection, context.organization_id)
        try:
            approval = self._prepare(connection, context, approval_id, _aware(now))
        except EngineError as exc:
            if exc.code != "not_found":
                raise
            return False
        if approval.status != "valid" or approval.approver_user_id is None or not approval.signature:
            return False
        fields = self._signed_fields(approval)
        return token_matches(fields, approval.signature, signing_key) and token_matches(fields, token, signing_key)

    def _signed_fields(self, approval: Approval) -> dict:
        return {
            "organization_id": approval.organization_id,
            "approver_user_id": approval.approver_user_id,
            "agent_version_id": approval.agent_version_id,
            "policy_version_id": approval.policy_version_id,
            "policy_version": approval.policy_version,
            "proposal_id": approval.proposal_id,
            "cart_hash": approval.cart_hash,
            "hash_version": approval.hash_version,
            "amount_minor": approval.amount_minor,
            "currency": approval.currency,
            "merchant_id": approval.merchant_id,
            "expires_at": stamp(approval.expires_at),
        }

    def _replay(self, connection, context, scope: str, key: str, request_hash: str, now: datetime) -> Approval | None:
        existing = connection.execute(
            _KEY,
            {"organization_id": context.organization_id, "scope": scope, "key": key},
        ).mappings().first()
        if existing is None:
            return None
        if existing["request_hash"] != request_hash:
            raise EngineError("idempotency_conflict", "That idempotency key was already used for a different approval.", 409)
        return self._prepare(connection, context, existing["resource_id"], now)

    def _remember(self, connection, context, scope: str, key: str, request_hash: str, resource_id: UUID) -> None:
        stored = connection.execute(
            _KEY,
            {"organization_id": context.organization_id, "scope": scope, "key": key},
        ).mappings().first()
        if stored is not None:
            return
        connection.execute(
            _INSERT_KEY,
            {
                "organization_id": context.organization_id,
                "scope": scope,
                "key": key,
                "request_hash": request_hash,
                "resource_id": resource_id,
            },
        )

    def _lock(self, connection, context, approval_id: UUID) -> None:
        locked = connection.execute(
            _LOCK,
            {"organization_id": context.organization_id, "approval_id": approval_id},
        ).first()
        if locked is None:
            raise EngineError("not_found", "That approval does not exist.", 404)

    def _load(self, connection, context, approval_id: UUID) -> Approval:
        row = connection.execute(
            _BY_ID,
            {"organization_id": context.organization_id, "approval_id": approval_id},
        ).mappings().first()
        if row is None:
            raise EngineError("not_found", "That approval does not exist.", 404)
        return _approval(row)

    def _prepare(self, connection, context, approval_id: UUID, now: datetime) -> Approval:
        approval = self._load(connection, context, approval_id)
        if approval.status in {"pending", "valid"} and now >= _aware(approval.expires_at):
            connection.execute(
                _STATUS,
                {"status": "expired", "organization_id": context.organization_id, "approval_id": approval_id},
            )
            append_event(
                connection,
                context,
                _event(context, "approval.expired", approval_id, {"approval_id": str(approval_id)}),
            )
            return self._load(connection, context, approval_id)
        if approval.status == "valid":
            _proposal, meta, digest = current_hash(connection, context.organization_id, approval.proposal_id)
            if digest != approval.cart_hash or digest != meta["stored_hash"]:
                connection.execute(
                    _STATUS,
                    {"status": "revoked", "organization_id": context.organization_id, "approval_id": approval_id},
                )
                append_event(
                    connection,
                    context,
                    _event(context, "approval.revoked", approval_id, {"approval_id": str(approval_id), "reason": "intent_mismatch"}),
                )
                return self._load(connection, context, approval_id)
        return approval
