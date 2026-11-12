"""Ask a model to draft policy rules, then hold that draft to the scripted truth.

The deterministic compiler in ``compiler.py`` owns a policy's hard numbers. A
model may propose the same rules in one pass, but ``check_model_draft`` rejects
any draft that disagrees with those numbers, hides an ambiguity, or tries to set
status. If the model is missing, misconfigured, or wrong, the caller falls back
to ``compile_scripted`` — the policy is never left to the model's discretion.
"""

import json

from mandate_core.contracts.models import ModelRef
from mandate_core.errors import EngineError
from mandate_core.models.registry import ProviderRegistry
from mandate_core.models.sync import run_sync
from mandate_core.models.types import ModelMessage, ModelRequest
from mandate_core.policy.compiler import check_model_draft

_SYSTEM = (
    "You translate a purchase instruction into a strict JSON policy draft. "
    "Return only JSON, no prose. Use these keys exactly: currency (always \"USD\"), "
    "maximum_total_minor (integer US cents), amount_includes (array), allowed_brands "
    "(array of brand names actually allowed), required_specs (object with ram_gb_min, "
    "storage_gb_min, storage_type), forbidden_addon_types (array), max_executions "
    "(integer >= 1), approval_required (boolean), preferences (array of soft wishes), "
    "ambiguities (array of strings naming anything vague that blocks activation), and "
    "original_instruction (the instruction verbatim). Never invent a number the "
    "instruction does not state. If a budget, brand, or spec is vague or missing, list "
    "it in ambiguities rather than guessing. Do not include a status field."
)


class ModelDrafter:
    """Wraps one provider + model id behind a ``draft(instruction)`` call."""

    def __init__(self, registry: ProviderRegistry, model: ModelRef):
        self.registry = registry
        self.model = model

    def draft(self, instruction: str) -> dict:
        """Return a validated draft, or raise EngineError so the caller falls back."""

        provider = self.registry.get(self.model.provider)
        request = ModelRequest(
            provider=self.model.provider,
            model=self.model.model,
            messages=(
                ModelMessage(role="system", content=_SYSTEM),
                ModelMessage(role="user", content=instruction),
            ),
            temperature=0,
            json_object=True,
        )
        response = run_sync(provider.invoke(request))
        try:
            raw = json.loads(response.content or "{}")
        except json.JSONDecodeError as exc:
            raise EngineError("compiler_invalid", "The model draft was not valid JSON.", 400) from exc
        return check_model_draft(instruction, raw)
