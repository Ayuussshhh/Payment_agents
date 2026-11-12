"""Pure purchase decision. The same policy version and cart always return the same result."""

from datetime import datetime, timezone
from uuid import UUID

from mandate_core.contracts import PolicyDecision
from mandate_core.policy.hashing import canonical_hash
from mandate_core.policy.money import ENABLED_CURRENCIES


def _now(value):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _field(item, key):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key)


def decide(mandate, proposal, now=None, reserved_minor=0, execution_count=0, has_matching_approval=False):
    """Return allow, deny, or needs_approval. Stop at the first deny."""

    current = _now(now)
    explanations = []

    def deny(code):
        explanations.append({"rule": code, "passed": False})
        return {
            "decision": "deny",
            "reason_code": code,
            "reason_codes": (code,),
            "cart_hash": None,
            "explanations": tuple(explanations),
        }

    def finish(decision, code, digest):
        explanations.append({"rule": code, "passed": True})
        return {
            "decision": decision,
            "reason_code": code,
            "reason_codes": (code,),
            "cart_hash": digest,
            "explanations": tuple(explanations),
        }

    if mandate.get("status") != "active":
        return deny("mandate_inactive")
    explanations.append({"rule": "mandate_inactive", "passed": True})
    if current >= _now(mandate["expires_at"]):
        return deny("mandate_expired")
    explanations.append({"rule": "mandate_expired", "passed": True})
    if proposal.get("mandate_version") != mandate.get("version"):
        return deny("stale_version")
    explanations.append({"rule": "stale_version", "passed": True})
    if proposal.get("currency") != mandate.get("currency") or proposal.get("currency") not in ENABLED_CURRENCIES:
        return deny("currency")
    explanations.append({"rule": "currency", "passed": True})

    total = proposal.get("total_minor")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        return deny("amount")

    summed = 0
    for line in proposal.get("lines") or []:
        quantity = _field(line, "quantity")
        unit = _field(line, "unit_amount_minor")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            return deny("amount")
        if not isinstance(unit, int) or isinstance(unit, bool) or unit < 0:
            return deny("amount")
        summed += unit * quantity
    explanations.append({"rule": "amount", "passed": True})
    if summed != total:
        return deny("total_mismatch")
    explanations.append({"rule": "total_mismatch", "passed": True})
    if total > mandate["maximum_total_minor"]:
        return deny("over_budget")
    explanations.append({"rule": "over_budget", "passed": True})

    allowed_brands = mandate.get("allowed_brands") or []
    forbidden = set(mandate.get("forbidden_addon_types") or [])
    for line in proposal["lines"]:
        if _field(line, "brand") not in allowed_brands:
            return deny("brand")
    explanations.append({"rule": "brand", "passed": True})
    for line in proposal["lines"]:
        if _field(line, "addon_type") in forbidden:
            return deny("addon")
    explanations.append({"rule": "addon", "passed": True})

    specs = mandate.get("required_specs") or {}
    for line in proposal["lines"]:
        if _field(line, "addon_type"):
            continue
        ram = _field(line, "ram_gb") or 0
        storage = _field(line, "storage_gb") or 0
        if "ram_gb_min" in specs and ram < specs["ram_gb_min"]:
            return deny("spec_ram")
        if "storage_gb_min" in specs and storage < specs["storage_gb_min"]:
            return deny("spec_storage")
        if "storage_type" in specs and _field(line, "storage_type") != specs["storage_type"]:
            return deny("spec_storage")
    explanations.append({"rule": "spec_ram", "passed": True})
    explanations.append({"rule": "spec_storage", "passed": True})

    digest = canonical_hash(proposal)
    if mandate.get("approval_required") and not has_matching_approval:
        return finish("needs_approval", "needs_approval", digest)
    if reserved_minor + total > mandate["maximum_total_minor"]:
        return deny("budget_exhausted")
    if execution_count >= mandate.get("max_executions", 1):
        return deny("execution_limit")
    return finish("allow", "allow", digest)


def execution_guard(approval, proposal, now=None):
    """Checks that belong to a later capture, including a cart that changed after approval."""

    current = _now(now)
    if approval.get("status") != "valid":
        return {"decision": "deny", "reason_code": "approval_replayed", "cart_hash": None}
    if current >= _now(approval["expires_at"]):
        return {"decision": "deny", "reason_code": "approval_expired", "cart_hash": None}
    digest = canonical_hash(proposal)
    if approval.get("cart_hash") != digest:
        return {"decision": "deny", "reason_code": "intent_mismatch", "cart_hash": digest}
    return {"decision": "allow", "reason_code": "allow", "cart_hash": digest}


def decision_from(result, mandate, proposal, policy_version_id: UUID) -> PolicyDecision:
    total = proposal.get("total_minor")
    maximum = mandate.get("maximum_total_minor")
    currency = proposal.get("currency")
    evaluated = total if isinstance(total, int) and not isinstance(total, bool) else None
    return PolicyDecision(
        decision=result["decision"],
        reason_codes=tuple(result["reason_codes"]),
        policy_version_id=policy_version_id,
        policy_version=int(mandate["version"]),
        cart_hash=result["cart_hash"],
        evaluated_amount_minor=evaluated,
        maximum_amount_minor=maximum if isinstance(maximum, int) and not isinstance(maximum, bool) else None,
        currency=currency if isinstance(currency, str) else None,
        explanations=tuple(result["explanations"]),
    )


def capture_action(approved_hash, current_hash):
    """A provider may capture a nearby amount. Mandate captures only the approved cart."""

    if approved_hash != current_hash:
        return "void"
    return "capture"
