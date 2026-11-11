from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mandate_core.contracts import EventEnvelope, ExecutionContext, Proposal, refuse_model_context
from mandate_core.errors import EngineError
from mandate_core.identity.catalog import expand_roles


def test_model_output_cannot_become_a_context():
    with pytest.raises(EngineError) as caught:
        refuse_model_context({"organization_id": "org", "permissions": ["approve:Approval"], "sku": "DELL"})
    assert caught.value.code == "context_mutation"
    with pytest.raises(ValidationError):
        ExecutionContext.model_validate({"organization_id": str(uuid4()), "permissions": ["read:Agent"], "sku": "DELL"})


def test_context_rejects_undeclared_fields():
    with pytest.raises(ValidationError):
        ExecutionContext(
            organization_id=uuid4(),
            user_id=uuid4(),
            request_id="req_test",
            status="active",
        )


def test_contract_models_reject_undeclared_fields():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        EventEnvelope(
            id=uuid4(),
            organization_id=uuid4(),
            name="agent.created",
            aggregate_type="agent",
            aggregate_id=uuid4(),
            actor_type="user",
            actor_id="user",
            request_id="req_test",
            payload={},
            occurred_at=now,
            status="active",
        )
    with pytest.raises(ValidationError):
        Proposal(
            currency="USD",
            mandate_id=uuid4(),
            mandate_version=1,
            seller={"id": "seller"},
            lines=(),
            total_minor=0,
            permissions=["approve:Approval"],
        )


def test_owner_expands_to_catalog_actions_and_developer_cannot_activate():
    owner = expand_roles(["owner"])
    developer = expand_roles(["developer"])
    assert "approve:Approval" in owner
    assert "activate:PolicyVersion" in owner
    assert "manage:all" not in owner
    assert "activate:PolicyVersion" not in developer
    assert "publish:AgentVersion" in developer
