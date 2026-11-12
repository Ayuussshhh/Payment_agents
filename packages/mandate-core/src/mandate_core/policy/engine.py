"""Store policy versions and call the pure evaluator. The evaluator does not open a connection."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from mandate_core.contracts import EventEnvelope, ExecutionContext, PolicyDecision, PolicyDraft, PolicyVersion, Proposal
from mandate_core.contracts.models import CartLine, Seller
from mandate_core.errors import EngineError
from mandate_core.events import append_event
from mandate_core.identity import authorize_action
from mandate_core.persistence.scope import use_tenant_scope
from mandate_core.persistence.catalog import get_catalog_item
from mandate_core.policy.compiler import compile_scripted
from mandate_core.policy.evaluate import decide, decision_from
from mandate_core.skills.catalog import get_product

_INSERT_POLICY = text(
    """
    insert into policies.policies (id, organization_id, name)
    values (:id, :organization_id, :name)
    """
)

_INSERT_VERSION = text(
    """
    insert into policies.policy_versions (
      id, organization_id, policy_id, version, status, currency, maximum_total_minor,
      constraints, original_instruction, ambiguities, preferences, expires_at
    )
    values (
      :id, :organization_id, :policy_id, :version, 'draft', :currency, :maximum_total_minor,
      cast(:constraints as jsonb), :original_instruction, cast(:ambiguities as jsonb),
      cast(:preferences as jsonb), :expires_at
    )
    returning id, organization_id, policy_id, version, status, currency, maximum_total_minor,
      constraints, original_instruction, ambiguities, preferences, expires_at, created_at, activated_at
    """
)

_NEXT_VERSION = text(
    """
    select coalesce(max(version), 0) + 1 as version
    from policies.policy_versions
    where policy_id = :policy_id and organization_id = :organization_id
    """
)

_LOCK_POLICY = text(
    """
    select id
    from policies.policies
    where id = :policy_id and organization_id = :organization_id
    for update
    """
)

_VERSION = text(
    """
    select v.id, v.organization_id, v.policy_id, p.name, v.version, v.status, v.currency,
           v.maximum_total_minor, v.constraints, v.original_instruction, v.ambiguities,
           v.preferences, v.expires_at, v.created_at, v.activated_at
    from policies.policy_versions v
    join policies.policies p on p.id = v.policy_id
    where v.organization_id = :organization_id and v.id = :version_id
    """
)

_LOCK_VERSION = text(
    """
    select v.id
    from policies.policy_versions v
    where v.organization_id = :organization_id and v.id = :version_id
    for update
    """
)

_LIST = text(
    """
    select v.id, v.organization_id, v.policy_id, p.name, v.version, v.status, v.currency,
           v.maximum_total_minor, v.constraints, v.original_instruction, v.ambiguities,
           v.preferences, v.expires_at, v.created_at, v.activated_at
    from policies.policy_versions v
    join policies.policies p on p.id = v.policy_id
    where v.organization_id = :organization_id
    order by v.created_at desc
    limit 200
    """
)

_ACTIVE = text(
    """
    select v.id
    from policies.policy_versions v
    where v.organization_id = :organization_id and v.policy_id = :policy_id and v.status = 'active'
    """
)

_LATEST = text(
    """
    select v.id
    from policies.policy_versions v
    where v.organization_id = :organization_id and v.policy_id = :policy_id
    order by v.version desc
    limit 1
    """
)

_RETIRE = text(
    """
    update policies.policy_versions
    set status = 'retired'
    where organization_id = :organization_id
      and policy_id = :policy_id
      and status = 'active'
      and id <> :version_id
    """
)

_ACTIVATE = text(
    """
    update policies.policy_versions
    set status = 'active', activated_at = :activated_at
    where organization_id = :organization_id and id = :version_id and status = 'draft'
    """
)

_KEY = text(
    """
    select resource_id, request_hash
    from policies.idempotency_keys
    where organization_id = :organization_id and scope = 'activate' and key = :key
    """
)

_INSERT_KEY = text(
    """
    insert into policies.idempotency_keys (organization_id, scope, key, request_hash, resource_id)
    values (:organization_id, 'activate', :key, :request_hash, :resource_id)
    """
)

_INSERT_EVALUATION = text(
    """
    insert into policies.evaluations (
      id, organization_id, policy_version_id, proposal_id, decision, reason_code,
      cart_hash, evaluated_amount_minor, result
    )
    values (
      :id, :organization_id, :policy_version_id, :proposal_id, :decision, :reason_code,
      :cart_hash, :evaluated_amount_minor, cast(:result as jsonb)
    )
    """
)

_EVALUATION = text(
    """
    select result
    from policies.evaluations
    where organization_id = :organization_id and id = :evaluation_id
    """
)


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _dumps(value) -> str:
    return json.dumps(value)


def _as_tuple(value) -> tuple:
    if not value:
        return ()
    if isinstance(value, str):
        value = json.loads(value)
    return tuple(value)


def _as_dict(value) -> dict:
    if not value:
        return {}
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


def _version(row, name: str | None = None) -> PolicyVersion:
    data = dict(row)
    if name is not None:
        data["name"] = name
    data["currency"] = str(data["currency"]).strip()
    data["ambiguities"] = _as_tuple(data["ambiguities"])
    data["preferences"] = _as_tuple(data["preferences"])
    data["constraints"] = _as_dict(data["constraints"])
    return PolicyVersion.model_validate(data)


def _require_user(context: ExecutionContext) -> None:
    if context.user_id is None:
        raise EngineError("unauthenticated", "A user is required.", 401)


def _mandate(version: PolicyVersion) -> dict:
    constraints = version.constraints
    return {
        "status": version.status,
        "version": version.version,
        "currency": version.currency,
        "maximum_total_minor": version.maximum_total_minor,
        "expires_at": version.expires_at,
        "allowed_brands": list(constraints.get("allowed_brands") or []),
        "required_specs": constraints.get("required_specs") or {},
        "forbidden_addon_types": list(constraints.get("forbidden_addon_types") or []),
        "max_executions": constraints.get("max_executions") or 1,
        "approval_required": bool(constraints.get("approval_required")),
    }


def evaluate_stored(
    version: PolicyVersion,
    proposal: Proposal,
    *,
    now: datetime | None = None,
    reserved_minor: int = 0,
    execution_count: int = 0,
    has_matching_approval: bool = False,
) -> PolicyDecision:
    """Decide from a loaded version. This function does not touch the database."""

    mandate = _mandate(version)
    body = proposal.model_dump()
    result = decide(
        mandate,
        body,
        now=now,
        reserved_minor=reserved_minor,
        execution_count=execution_count,
        has_matching_approval=has_matching_approval,
    )
    return decision_from(result, mandate, body, version.id)


def proposal_for_sku(policy_id: UUID, version: int, sku: str, suggested_unit_amount_minor: int | None = None, *, product: dict | None = None) -> Proposal:
    """Build a cart from the catalog. A model-suggested price is not read."""

    del suggested_unit_amount_minor
    product = product or get_product(sku)
    if product is None:
        raise EngineError("skill_invalid", "That sku is not in the catalog.", 400)
    line = CartLine(
        sku=product["sku"],
        brand=product["brand"],
        quantity=1,
        unit_amount_minor=product["unit_amount_minor"],
        ram_gb=product["ram_gb"],
        storage_gb=product["storage_gb"],
        storage_type=product["storage_type"],
    )
    return Proposal(
        currency=product.get("currency", "USD"),
        mandate_id=policy_id,
        mandate_version=version,
        seller=Seller(id="catalog"),
        lines=(line,),
        total_minor=product["unit_amount_minor"],
    )


def _constraints(compiled: dict) -> dict:
    return {
        "amount_includes": compiled["amount_includes"],
        "allowed_brands": compiled["allowed_brands"],
        "required_specs": compiled["required_specs"],
        "forbidden_addon_types": compiled["forbidden_addon_types"],
        "max_executions": compiled["max_executions"],
        "approval_required": compiled["approval_required"],
    }


def _stated_maximum(compiled: dict) -> int:
    stated = compiled.get("stated_maximum_minor") or 0
    if isinstance(stated, bool) or not isinstance(stated, int) or stated <= 0:
        raise EngineError(
            "compiler_invalid",
            "The instruction has no single maximum the engine can store.",
            400,
            {"ambiguities": list(compiled.get("ambiguities") or [])},
        )
    return stated


def _policy_name(compiled: dict) -> str:
    brands = [brand for brand in compiled["allowed_brands"] if brand != "unspecified"]
    if len(brands) == 1:
        return f"{brands[0]} purchase"
    return "Purchase policy"


def _require_activatable(version: PolicyVersion) -> None:
    if version.ambiguities:
        raise EngineError(
            "compiler_invalid",
            "A draft with ambiguities cannot be activated.",
            400,
            {"ambiguities": list(version.ambiguities)},
        )
    constraints = version.constraints
    try:
        PolicyDraft(
            currency=version.currency,
            maximum_total_minor=version.maximum_total_minor,
            amount_includes=tuple(constraints["amount_includes"]),
            allowed_brands=tuple(constraints["allowed_brands"]),
            required_specs=constraints["required_specs"],
            forbidden_addon_types=tuple(constraints["forbidden_addon_types"]),
            max_executions=constraints["max_executions"],
            approval_required=constraints["approval_required"],
            preferences=version.preferences,
            ambiguities=version.ambiguities,
            original_instruction=version.original_instruction,
        )
    except ValidationError as exc:
        raise EngineError("compiler_invalid", "The draft failed schema validation.", 400) from exc


def _event(context: ExecutionContext, name: str, policy_id: UUID, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        id=uuid4(),
        organization_id=context.organization_id,
        name=name,
        aggregate_type="policy",
        aggregate_id=policy_id,
        actor_type="user",
        actor_id=str(context.user_id),
        request_id=context.request_id,
        payload=payload,
        occurred_at=datetime.now(timezone.utc),
    )


def _compile(instruction: str, drafter) -> dict:
    """Prefer a model draft that matches the scripted truth; fall back to scripted.

    A drafter may be None (no model configured). Any disagreement, bad output, or
    provider failure raises inside ``drafter.draft`` and we use the deterministic
    compiler instead, so a misbehaving model can never change a policy's rules.
    """

    if drafter is not None:
        try:
            drafted = drafter.draft(instruction)
            if drafted is not None:
                return drafted
        except EngineError:
            pass
        except Exception:
            pass
    return compile_scripted(instruction)


def _request_hash(version_id: UUID) -> str:
    return hashlib.sha256(f"activate:{version_id}".encode()).hexdigest()


class PolicyEngine:
    def create_draft(self, connection: Connection, context: ExecutionContext, instruction: str, now: datetime | None = None, drafter=None) -> PolicyVersion:
        _require_user(context)
        authorize_action(context, "create", "Policy")
        compiled = _compile(instruction, drafter)
        return self._insert_version(connection, context, uuid4(), 1, compiled, _policy_name(compiled), now, created=True)

    def add_version(self, connection: Connection, context: ExecutionContext, policy_id: UUID, instruction: str, now: datetime | None = None, drafter=None) -> PolicyVersion:
        _require_user(context)
        authorize_action(context, "create", "Policy")
        use_tenant_scope(connection, context.organization_id)
        locked = connection.execute(
            _LOCK_POLICY,
            {"policy_id": policy_id, "organization_id": context.organization_id},
        ).first()
        if locked is None:
            raise EngineError("not_found", "That policy does not exist.", 404)
        compiled = _compile(instruction, drafter)
        version = connection.execute(
            _NEXT_VERSION,
            {"policy_id": policy_id, "organization_id": context.organization_id},
        ).scalar_one()
        name = connection.execute(
            text("select name from policies.policies where id = :policy_id and organization_id = :organization_id"),
            {"policy_id": policy_id, "organization_id": context.organization_id},
        ).scalar_one()
        return self._insert_version(connection, context, policy_id, version, compiled, name, now, created=False)

    def _insert_version(self, connection, context, policy_id, version, compiled, name, now, created: bool) -> PolicyVersion:
        stated = _stated_maximum(compiled)
        if created:
            use_tenant_scope(connection, context.organization_id)
            connection.execute(
                _INSERT_POLICY,
                {"id": policy_id, "organization_id": context.organization_id, "name": name},
            )
        version_id = uuid4()
        row = connection.execute(
            _INSERT_VERSION,
            {
                "id": version_id,
                "organization_id": context.organization_id,
                "policy_id": policy_id,
                "version": version,
                "currency": compiled["currency"],
                "maximum_total_minor": stated,
                "constraints": _dumps(_constraints(compiled)),
                "original_instruction": compiled["original_instruction"],
                "ambiguities": _dumps(list(compiled["ambiguities"])),
                "preferences": _dumps(list(compiled["preferences"])),
                "expires_at": _aware(now) + timedelta(days=7),
            },
        ).mappings().one()
        stored = _version(row, name)
        if created:
            append_event(
                connection,
                context,
                _event(context, "policy.created", policy_id, {"policy_id": str(policy_id), "version_id": str(version_id)}),
            )
        return stored

    def list_versions(self, connection: Connection, context: ExecutionContext) -> list[PolicyVersion]:
        _require_user(context)
        authorize_action(context, "read", "Policy")
        use_tenant_scope(connection, context.organization_id)
        rows = connection.execute(_LIST, {"organization_id": context.organization_id}).mappings()
        return [_version(row) for row in rows]

    def get_version(self, connection: Connection, context: ExecutionContext, version_id: UUID) -> PolicyVersion:
        _require_user(context)
        authorize_action(context, "read", "PolicyVersion")
        use_tenant_scope(connection, context.organization_id)
        row = connection.execute(
            _VERSION,
            {"organization_id": context.organization_id, "version_id": version_id},
        ).mappings().first()
        if row is None:
            raise EngineError("not_found", "That policy version does not exist.", 404)
        return _version(row)

    def activate(self, connection: Connection, context: ExecutionContext, version_id: UUID, idempotency_key: str, now: datetime | None = None) -> PolicyVersion:
        _require_user(context)
        authorize_action(context, "activate", "PolicyVersion")
        if not idempotency_key:
            raise EngineError("idempotency_key_required", "An Idempotency-Key header is required.", 400)
        use_tenant_scope(connection, context.organization_id)
        request_hash = _request_hash(version_id)
        existing = connection.execute(
            _KEY,
            {"organization_id": context.organization_id, "key": idempotency_key},
        ).mappings().first()
        if existing is not None:
            if existing["request_hash"] != request_hash:
                raise EngineError("idempotency_conflict", "That idempotency key was already used for a different activation.", 409)
            return self._load_version(connection, context, existing["resource_id"])
        locked = connection.execute(
            _LOCK_VERSION,
            {"organization_id": context.organization_id, "version_id": version_id},
        ).first()
        if locked is None:
            raise EngineError("not_found", "That policy version does not exist.", 404)
        current = self._load_version(connection, context, version_id)
        if current.status == "retired":
            raise EngineError("version_immutable", "A retired policy version cannot be activated.", 409)
        if current.status == "draft":
            _require_activatable(current)
            connection.execute(
                _LOCK_POLICY,
                {"policy_id": current.policy_id, "organization_id": context.organization_id},
            )
            connection.execute(
                _RETIRE,
                {
                    "organization_id": context.organization_id,
                    "policy_id": current.policy_id,
                    "version_id": version_id,
                },
            )
            connection.execute(
                _ACTIVATE,
                {
                    "organization_id": context.organization_id,
                    "version_id": version_id,
                    "activated_at": _aware(now),
                },
            )
            append_event(
                connection,
                context,
                _event(
                    context,
                    "policy.activated",
                    current.policy_id,
                    {"policy_id": str(current.policy_id), "version_id": str(version_id)},
                ),
            )
        connection.execute(
            _INSERT_KEY,
            {
                "organization_id": context.organization_id,
                "key": idempotency_key,
                "request_hash": request_hash,
                "resource_id": version_id,
            },
        )
        return self._load_version(connection, context, version_id)

    def _load_version(self, connection, context, version_id) -> PolicyVersion:
        row = connection.execute(
            _VERSION,
            {"organization_id": context.organization_id, "version_id": version_id},
        ).mappings().first()
        if row is None:
            raise EngineError("not_found", "That policy version does not exist.", 404)
        return _version(row)

    def evaluate_sku(
        self,
        connection: Connection,
        context: ExecutionContext,
        policy_id: UUID,
        sku: str,
        *,
        now: datetime | None = None,
        suggested_unit_amount_minor: int | None = None,
    ) -> tuple[PolicyDecision, UUID, UUID]:
        _require_user(context)
        authorize_action(context, "create", "Policy")
        use_tenant_scope(connection, context.organization_id)
        version_id = connection.execute(
            _ACTIVE,
            {"organization_id": context.organization_id, "policy_id": policy_id},
        ).scalar()
        if version_id is None:
            version_id = connection.execute(
                _LATEST,
                {"organization_id": context.organization_id, "policy_id": policy_id},
            ).scalar()
        if version_id is None:
            raise EngineError("not_found", "That policy does not exist.", 404)
        version = self._load_version(connection, context, version_id)
        product = get_catalog_item(connection, context.organization_id, sku)
        if product is None:
            raise EngineError("skill_invalid", "That SKU is not in this workspace catalog.", 400)
        if str(product.get("currency", "USD")).strip().upper() != version.currency.upper():
            raise EngineError(
                "currency_mismatch",
                "The catalog item's currency must match the selected policy currency.",
                409,
            )
        proposal = proposal_for_sku(policy_id, version.version, sku, suggested_unit_amount_minor, product=product)
        decision = evaluate_stored(version, proposal, now=now)
        evaluation_id = uuid4()
        proposal_id = uuid4()
        if decision.cart_hash:
            from mandate_core.commerce.carts import store_cart

            proposal_id = store_cart(
                connection,
                context.organization_id,
                version.id,
                proposal,
                decision.cart_hash,
                context.run_id,
                sku,
            )
        connection.execute(
            _INSERT_EVALUATION,
            {
                "id": evaluation_id,
                "organization_id": context.organization_id,
                "policy_version_id": version.id,
                "proposal_id": proposal_id,
                "decision": decision.decision,
                "reason_code": decision.reason_codes[0],
                "cart_hash": decision.cart_hash,
                "evaluated_amount_minor": decision.evaluated_amount_minor,
                "result": decision.model_dump_json(),
            },
        )
        append_event(
            connection,
            context,
            _event(
                context,
                "policy.evaluated",
                policy_id,
                {
                    "policy_id": str(policy_id),
                    "version_id": str(version.id),
                    "evaluation_id": str(evaluation_id),
                    "decision": decision.decision,
                    "reason_code": decision.reason_codes[0],
                },
            ),
        )
        return decision, evaluation_id, proposal_id

    def explain(self, connection: Connection, context: ExecutionContext, evaluation_id: UUID) -> PolicyDecision:
        _require_user(context)
        authorize_action(context, "read", "PolicyVersion")
        use_tenant_scope(connection, context.organization_id)
        result = connection.execute(
            _EVALUATION,
            {"organization_id": context.organization_id, "evaluation_id": evaluation_id},
        ).scalar()
        if result is None:
            raise EngineError("not_found", "That evaluation does not exist.", 404)
        if isinstance(result, str):
            return PolicyDecision.model_validate_json(result)
        return PolicyDecision.model_validate(result)

    def replace_constraints(self, connection: Connection, context: ExecutionContext, version_id: UUID) -> None:
        """Attempt an in-place edit. The database rejects it and the caller rolls back."""

        use_tenant_scope(connection, context.organization_id)
        try:
            result = connection.execute(
                text(
                    """
                    update policies.policy_versions
                    set maximum_total_minor = maximum_total_minor + 1
                    where id = :version_id and organization_id = :organization_id
                    """
                ),
                {"version_id": version_id, "organization_id": context.organization_id},
            )
        except DBAPIError as exc:
            raise EngineError("version_immutable", "A policy version cannot be edited.", 409) from exc
        if result.rowcount == 0:
            raise EngineError("not_found", "That policy version does not exist.", 404)
        raise EngineError("version_immutable", "A policy version cannot be edited.", 409)
