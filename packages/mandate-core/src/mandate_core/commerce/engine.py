"""The commerce state machine. It decides what to charge; the provider only carries it.

prepare reloads the cart from catalog prices, checks the approval against the
current hash, reserves budget under a row lock, then creates the provider order.
capture re-runs the guard: the approved cart captures, a changed cart voids with
reason intent_mismatch. The database row is the authority throughout — a provider
willing to charge a nearby amount never changes the outcome.
"""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.commerce.carts import current_hash
from mandate_core.commerce.provider import (
    AuthorizeOrder,
    CaptureOrder,
    CreateOrder,
    PaymentProvider,
    RefundOrder,
    VoidOrder,
)
from mandate_core.contracts import EventEnvelope, ExecutionContext, Transaction
from mandate_core.errors import EngineError
from mandate_core.events import append_event
from mandate_core.identity import authorize_action
from mandate_core.persistence.scope import use_tenant_scope
from mandate_core.policy.evaluate import execution_guard

_INSERT_TXN = text(
    """
    insert into commerce.transactions (
      id, organization_id, proposal_id, approval_id, policy_version_id, cart_hash,
      amount_minor, currency, status, provider, idempotency_key
    )
    values (
      :id, :organization_id, :proposal_id, :approval_id, :policy_version_id, :cart_hash,
      :amount_minor, :currency, :status, :provider, :idempotency_key
    )
    """
)

_TXN = text(
    """
    select id, organization_id, proposal_id, approval_id, policy_version_id, cart_hash,
           amount_minor, currency, status, provider, provider_order_id, provider_authorization_id,
           provider_capture_id, provider_approval_url, reason_code, idempotency_key, created_at, updated_at
    from commerce.transactions
    where organization_id = :organization_id and id = :transaction_id
    """
)

_TXN_BY_KEY = text(
    """
    select id from commerce.transactions
    where organization_id = :organization_id and idempotency_key = :idempotency_key
    """
)

_UPDATE_TXN = text(
    """
    update commerce.transactions
    set status = :status,
        provider_order_id = coalesce(:provider_order_id, provider_order_id),
        provider_authorization_id = coalesce(:provider_authorization_id, provider_authorization_id),
        provider_capture_id = coalesce(:provider_capture_id, provider_capture_id),
        provider_approval_url = coalesce(:provider_approval_url, provider_approval_url),
        reason_code = :reason_code,
        updated_at = now()
    where organization_id = :organization_id and id = :transaction_id
    """
)

_LOCK_POLICY_MAX = text(
    """
    select maximum_total_minor from policies.policy_versions
    where organization_id = :organization_id and id = :policy_version_id
    for update
    """
)

_RESERVED_SUM = text(
    """
    select coalesce(sum(amount_minor), 0) as held
    from commerce.budget_reservations
    where organization_id = :organization_id and policy_version_id = :policy_version_id
      and status in ('held', 'captured')
    """
)

_INSERT_RESERVATION = text(
    """
    insert into commerce.budget_reservations (
      id, organization_id, policy_version_id, transaction_id, amount_minor, status
    )
    values (:id, :organization_id, :policy_version_id, :transaction_id, :amount_minor, 'held')
    """
)

_RESERVATION_STATUS = text(
    """
    update commerce.budget_reservations
    set status = :status
    where organization_id = :organization_id and transaction_id = :transaction_id
    """
)

_APPROVAL = text(
    """
    select id, proposal_id, policy_version_id, agent_version_id, cart_hash, amount_minor,
           currency, merchant_id, status, expires_at
    from approvals.approvals
    where organization_id = :organization_id and id = :approval_id
    """
)

_CONSUME_APPROVAL = text(
    """
    update approvals.approvals set status = 'consumed'
    where organization_id = :organization_id and id = :approval_id and status = 'valid'
    """
)

_INSERT_ATTEMPT = text(
    """
    insert into commerce.payment_attempts (
      id, transaction_id, operation, request_id, provider_status, raw_response
    )
    values (:id, :transaction_id, :operation, :request_id, :provider_status, cast(:raw_response as jsonb))
    on conflict (transaction_id, operation, request_id) do nothing
    """
)

_ATTEMPTS = text(
    """
    select operation, request_id, provider_status, raw_response, created_at
    from commerce.payment_attempts
    where transaction_id = :transaction_id
    order by created_at, operation
    """
)


def _require_user(context: ExecutionContext) -> None:
    if context.user_id is None:
        raise EngineError("unauthenticated", "A user is required for a payment.", 401)


def _require_key(key: str) -> None:
    if not key:
        raise EngineError("idempotency_key_required", "An Idempotency-Key header is required.", 400)


def _event(context: ExecutionContext, name: str, transaction_id: UUID, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        id=uuid4(),
        organization_id=context.organization_id,
        name=name,
        aggregate_type="transaction",
        aggregate_id=transaction_id,
        actor_type="user",
        actor_id=str(context.user_id),
        request_id=context.request_id,
        payload=payload,
        occurred_at=datetime.now(timezone.utc),
    )


def _transaction(row) -> Transaction:
    return Transaction(
        id=row["id"],
        organization_id=row["organization_id"],
        proposal_id=row["proposal_id"],
        approval_id=row["approval_id"],
        policy_version_id=row["policy_version_id"],
        cart_hash=row["cart_hash"],
        amount_minor=row["amount_minor"],
        currency=str(row["currency"]).strip(),
        status=row["status"],
        provider=row["provider"],
        provider_order_id=row["provider_order_id"],
        provider_authorization_id=row["provider_authorization_id"],
        provider_capture_id=row["provider_capture_id"],
        provider_approval_url=row["provider_approval_url"],
        reason_code=row["reason_code"],
        idempotency_key=row["idempotency_key"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class CommerceEngine:
    def __init__(self, provider: PaymentProvider | None = None):
        self.provider = provider

    # ---- reads -------------------------------------------------------------

    def get(self, connection: Connection, context: ExecutionContext, transaction_id: UUID) -> Transaction:
        _require_user(context)
        authorize_action(context, "read", "Transaction")
        use_tenant_scope(connection, context.organization_id)
        row = self._row(connection, context, transaction_id)
        return _transaction(row)

    def attempts(self, connection: Connection, context: ExecutionContext, transaction_id: UUID) -> list[dict]:
        use_tenant_scope(connection, context.organization_id)
        rows = connection.execute(_ATTEMPTS, {"transaction_id": transaction_id}).mappings().all()
        return [
            {
                "operation": row["operation"],
                "request_id": row["request_id"],
                "provider_status": row["provider_status"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

    # ---- state machine -----------------------------------------------------

    async def prepare(self, connection: Connection, context: ExecutionContext, proposal_id: UUID, approval_id: UUID, idempotency_key: str) -> Transaction:
        _require_user(context)
        authorize_action(context, "execute", "Transaction")
        _require_key(idempotency_key)
        use_tenant_scope(connection, context.organization_id)

        replay = connection.execute(
            _TXN_BY_KEY, {"organization_id": context.organization_id, "idempotency_key": idempotency_key}
        ).first()
        if replay is not None:
            return _transaction(self._row(connection, context, replay[0]))

        approval = connection.execute(
            _APPROVAL, {"organization_id": context.organization_id, "approval_id": approval_id}
        ).mappings().first()
        if approval is None:
            raise EngineError("not_found", "That approval does not exist.", 404)
        if approval["proposal_id"] != proposal_id:
            raise EngineError("approval_mismatch", "That approval is for a different cart.", 409)

        proposal, _meta, _hash = current_hash(connection, context.organization_id, proposal_id)
        guard = execution_guard(
            {"status": approval["status"], "expires_at": approval["expires_at"], "cart_hash": approval["cart_hash"]},
            proposal,
        )
        if guard["decision"] != "allow":
            raise EngineError(guard["reason_code"], "The approved cart is no longer valid.", 409)

        amount = approval["amount_minor"]
        policy_version_id = approval["policy_version_id"]
        maximum = connection.execute(
            _LOCK_POLICY_MAX, {"organization_id": context.organization_id, "policy_version_id": policy_version_id}
        ).scalar()
        if maximum is None:
            raise EngineError("not_found", "That policy version does not exist.", 404)
        held = connection.execute(
            _RESERVED_SUM, {"organization_id": context.organization_id, "policy_version_id": policy_version_id}
        ).scalar() or 0
        if held + amount > maximum:
            raise EngineError("budget_exhausted", "Pending reservations plus this total exceed the maximum.", 409)

        transaction_id = uuid4()
        connection.execute(
            _INSERT_TXN,
            {
                "id": transaction_id,
                "organization_id": context.organization_id,
                "proposal_id": proposal_id,
                "approval_id": approval_id,
                "policy_version_id": policy_version_id,
                "cart_hash": approval["cart_hash"],
                "amount_minor": amount,
                "currency": approval["currency"],
                "status": "prepared",
                "provider": self.provider.name,
                "idempotency_key": idempotency_key,
            },
        )
        connection.execute(
            _INSERT_RESERVATION,
            {
                "id": uuid4(),
                "organization_id": context.organization_id,
                "policy_version_id": policy_version_id,
                "transaction_id": transaction_id,
                "amount_minor": amount,
            },
        )

        command = CreateOrder(
            transaction_id=str(transaction_id),
            amount_minor=amount,
            currency=str(approval["currency"]).strip(),
            merchant_id=approval["merchant_id"],
            catalog_sku=_meta["catalog_sku"],
        )
        result, outcome = await self._attempt(self.provider.create_order(command))
        self._record(connection, transaction_id, "create", str(transaction_id), result, outcome)
        if outcome == "ok":
            self._set(connection, context, transaction_id, "reserved", provider_order_id=result.provider_order_id, provider_approval_url=result.approval_url)
            self._emit(connection, context, "commerce.order.created", transaction_id, {"amount_minor": amount})
        elif outcome == "timeout":
            self._set(connection, context, transaction_id, "unknown", reason_code="provider_timeout")
            self._emit(connection, context, "commerce.order.unknown", transaction_id, {})
        else:
            self._release(connection, context, transaction_id)
            self._set(connection, context, transaction_id, "failed", reason_code="provider_refused")
            self._emit(connection, context, "commerce.order.failed", transaction_id, {})
        return _transaction(self._row(connection, context, transaction_id))

    async def authorize(self, connection: Connection, context: ExecutionContext, transaction_id: UUID, provider_order_id: str) -> Transaction:
        txn = self._begin(connection, context, transaction_id, "execute")
        if txn.status == "authorized" and txn.provider_order_id == provider_order_id:
            return txn
        if txn.status != "reserved":
            raise EngineError("invalid_state", f"A payment cannot be authorized from {txn.status}.", 409)
        if provider_order_id != txn.provider_order_id:
            raise EngineError("order_mismatch", "That order id is not the one this payment created.", 409)
        command = AuthorizeOrder(transaction_id=str(transaction_id), provider_order_id=provider_order_id)
        result, outcome = await self._attempt(self.provider.authorize(command))
        self._record(connection, transaction_id, "authorize", str(transaction_id), result, outcome)
        if outcome == "ok":
            self._set(connection, context, transaction_id, "authorized", provider_authorization_id=result.provider_authorization_id)
            self._emit(connection, context, "commerce.payment.authorized", transaction_id, {})
        elif outcome == "timeout":
            self._set(connection, context, transaction_id, "unknown", reason_code="authorize_timeout")
        else:
            raise EngineError("provider_error", "The provider refused to authorize the order.", 502)
        return _transaction(self._row(connection, context, transaction_id))

    async def capture(self, connection: Connection, context: ExecutionContext, transaction_id: UUID) -> Transaction:
        txn = self._begin(connection, context, transaction_id, "execute")
        if txn.status in {"captured", "voided"}:
            return txn
        if txn.status != "authorized":
            raise EngineError("invalid_state", f"A payment cannot be captured from {txn.status}.", 409)

        proposal, _meta, _hash = current_hash(connection, context.organization_id, txn.proposal_id)
        approval = connection.execute(
            _APPROVAL, {"organization_id": context.organization_id, "approval_id": txn.approval_id}
        ).mappings().first()
        guard = execution_guard(
            {"status": approval["status"], "expires_at": approval["expires_at"], "cart_hash": approval["cart_hash"]},
            proposal,
        )
        if guard["decision"] != "allow":
            command = VoidOrder(transaction_id=str(transaction_id), provider_order_id=txn.provider_order_id, provider_authorization_id=txn.provider_authorization_id)
            result, outcome = await self._attempt(self.provider.void(command))
            self._record(connection, transaction_id, "void", str(transaction_id), result, outcome)
            self._release(connection, context, transaction_id)
            self._set(connection, context, transaction_id, "voided", reason_code=guard["reason_code"])
            self._emit(connection, context, "commerce.payment.voided", transaction_id, {"reason_code": guard["reason_code"]})
            return _transaction(self._row(connection, context, transaction_id))

        command = CaptureOrder(transaction_id=str(transaction_id), provider_order_id=txn.provider_order_id, provider_authorization_id=txn.provider_authorization_id)
        result, outcome = await self._attempt(self.provider.capture(command))
        self._record(connection, transaction_id, "capture", str(transaction_id), result, outcome)
        if outcome == "ok":
            connection.execute(_RESERVATION_STATUS, {"status": "captured", "organization_id": context.organization_id, "transaction_id": transaction_id})
            connection.execute(_CONSUME_APPROVAL, {"organization_id": context.organization_id, "approval_id": txn.approval_id})
            self._set(connection, context, transaction_id, "captured", provider_capture_id=result.provider_capture_id)
            self._emit(connection, context, "commerce.payment.captured", transaction_id, {"amount_minor": txn.amount_minor})
        elif outcome == "timeout":
            self._set(connection, context, transaction_id, "unknown", reason_code="capture_timeout")
        else:
            raise EngineError("provider_error", "The provider refused to capture the authorization.", 502)
        return _transaction(self._row(connection, context, transaction_id))

    async def void(self, connection: Connection, context: ExecutionContext, transaction_id: UUID) -> Transaction:
        txn = self._begin(connection, context, transaction_id, "execute")
        if txn.status == "voided":
            return txn
        if txn.status not in {"reserved", "authorized"}:
            raise EngineError("invalid_state", f"A payment cannot be voided from {txn.status}.", 409)
        command = VoidOrder(transaction_id=str(transaction_id), provider_order_id=txn.provider_order_id, provider_authorization_id=txn.provider_authorization_id)
        result, outcome = await self._attempt(self.provider.void(command))
        self._record(connection, transaction_id, "void", str(transaction_id), result, outcome)
        self._release(connection, context, transaction_id)
        self._set(connection, context, transaction_id, "voided", reason_code="explicit_void")
        self._emit(connection, context, "commerce.payment.voided", transaction_id, {"reason_code": "explicit_void"})
        return _transaction(self._row(connection, context, transaction_id))

    async def refund(self, connection: Connection, context: ExecutionContext, transaction_id: UUID, amount_minor: int | None = None) -> Transaction:
        txn = self._begin(connection, context, transaction_id, "execute")
        if txn.status == "refunded":
            return txn
        if txn.status != "captured":
            raise EngineError("invalid_state", f"A payment cannot be refunded from {txn.status}.", 409)
        if amount_minor is not None and amount_minor != txn.amount_minor:
            raise EngineError("partial_refund_unsupported", "Only a full refund is supported in this release.", 400)
        command = RefundOrder(transaction_id=str(transaction_id), provider_capture_id=txn.provider_capture_id, amount_minor=txn.amount_minor, currency=txn.currency)
        result, outcome = await self._attempt(self.provider.refund(command))
        self._record(connection, transaction_id, "refund", str(transaction_id), result, outcome)
        if outcome == "ok":
            self._set(connection, context, transaction_id, "refunded", reason_code="refunded")
            self._emit(connection, context, "commerce.payment.refunded", transaction_id, {"amount_minor": txn.amount_minor})
        else:
            raise EngineError("provider_error", "The provider refused the refund.", 502)
        return _transaction(self._row(connection, context, transaction_id))

    # ---- helpers -----------------------------------------------------------

    def _begin(self, connection, context, transaction_id, action) -> Transaction:
        _require_user(context)
        authorize_action(context, action, "Transaction")
        use_tenant_scope(connection, context.organization_id)
        return _transaction(self._row(connection, context, transaction_id))

    def _row(self, connection, context, transaction_id):
        row = connection.execute(
            _TXN, {"organization_id": context.organization_id, "transaction_id": transaction_id}
        ).mappings().first()
        if row is None:
            raise EngineError("not_found", "That payment does not exist.", 404)
        return row

    def _set(self, connection, context, transaction_id, status, provider_order_id=None, provider_authorization_id=None, provider_capture_id=None, provider_approval_url=None, reason_code=""):
        connection.execute(
            _UPDATE_TXN,
            {
                "organization_id": context.organization_id,
                "transaction_id": transaction_id,
                "status": status,
                "provider_order_id": provider_order_id,
                "provider_authorization_id": provider_authorization_id,
                "provider_capture_id": provider_capture_id,
                "provider_approval_url": provider_approval_url,
                "reason_code": reason_code,
            },
        )

    def _release(self, connection, context, transaction_id):
        connection.execute(_RESERVATION_STATUS, {"status": "released", "organization_id": context.organization_id, "transaction_id": transaction_id})

    def _record(self, connection, transaction_id, operation, request_id, result, outcome):
        status = result.status if result is not None else outcome
        raw = json.dumps(result.raw if result is not None else {"outcome": outcome})
        connection.execute(
            _INSERT_ATTEMPT,
            {
                "id": uuid4(),
                "transaction_id": transaction_id,
                "operation": operation,
                "request_id": request_id,
                "provider_status": status,
                "raw_response": raw,
            },
        )

    def _emit(self, connection, context, name, transaction_id, payload):
        append_event(connection, context, _event(context, name, transaction_id, payload))

    async def _attempt(self, coro):
        try:
            result = await coro
            return result, "ok"
        except TimeoutError:
            return None, "timeout"
        except httpx.TimeoutException:
            return None, "timeout"
        except EngineError as exc:
            if exc.code in {"provider_error", "provider_unconfigured", "provider_live_refused"}:
                return None, "refused"
            raise
        except Exception:
            return None, "refused"
