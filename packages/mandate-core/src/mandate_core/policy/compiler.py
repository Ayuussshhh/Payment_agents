"""Turn an instruction into a draft. Activation is a separate action."""

import re

from pydantic import ValidationError

from mandate_core.contracts import PolicyDraft
from mandate_core.errors import EngineError

_ENGINE_KEYS = {"activatable", "stated_maximum_minor"}


def accept_compiler_payload(raw) -> dict:
    """Reject anything the model is not allowed to decide, including status."""

    if not isinstance(raw, dict):
        raise EngineError("compiler_invalid", "Compiler output was not an object.", 400)
    if "status" in raw:
        raise EngineError("compiler_overreach", "The compiler cannot set policy status.", 409)
    payload = {key: value for key, value in raw.items() if key not in _ENGINE_KEYS}
    amount = payload.get("maximum_total_minor")
    if amount is not None and (isinstance(amount, bool) or not isinstance(amount, int)):
        raise EngineError("compiler_invalid", "maximum_total_minor must be an integer number of minor units.", 400)
    try:
        draft = PolicyDraft.model_validate(payload)
    except ValidationError as exc:
        raise EngineError("compiler_invalid", "The draft failed schema validation.", 400) from exc
    if draft.currency != "USD":
        raise EngineError("currency", "Only USD policies can be compiled.", 400)
    return draft.model_dump()


def _dollars_to_minor(raw: str) -> int:
    cleaned = raw.replace(",", "")
    if "." in cleaned:
        whole, fraction = cleaned.split(".", 1)
        fraction = (fraction + "00")[:2]
        return int(whole) * 100 + int(fraction)
    return int(cleaned) * 100


def compile_scripted(instruction: str) -> dict:
    """Read the hard numbers. Vague phrases stay ambiguities and cannot activate."""

    text = " ".join(instruction.split())
    lowered = text.lower()
    ambiguities = []
    preferences = []

    if re.search(r"\baround\b", lowered):
        ambiguities.append("“around” is not a hard maximum. State a number the engine can refuse.")
    if re.search(r"\bgood laptop\b", lowered):
        ambiguities.append("“a good laptop” is not a specification.")
    if "or something similar" in lowered:
        ambiguities.append("“or something similar” would expand the brand. Name the brand.")
    if "good battery life" in lowered:
        preferences.append("good battery life")
    if "good performance" in lowered:
        preferences.append("good performance")

    amounts = [_dollars_to_minor(match) for match in re.findall(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text)]
    stated = amounts[0] if len(amounts) == 1 else 0
    maximum = None
    if len(amounts) > 1:
        ambiguities.append("The instruction states more than one amount. Activation needs a single maximum.")
    elif len(amounts) == 1 and not any("around" in item for item in ambiguities):
        maximum = amounts[0]

    brands = []
    if re.search(r"\bdell\b", lowered):
        brands.append("Dell")
    if re.search(r"\bhp\b", lowered):
        brands.append("HP")
    if len(brands) > 1:
        ambiguities.append("More than one brand is named. Choose the brands that are actually allowed.")
        allowed = []
    else:
        allowed = brands
    if not allowed and not any("brand" in item for item in ambiguities):
        ambiguities.append("No brand was named. The engine will not guess one.")

    ram_match = re.search(r"(\d+)\s*gb(?:\s+of)?\s+ram", lowered)
    storage_match = re.search(r"(\d+)\s*gb\s+ssd", lowered)
    specs = {
        "ram_gb_min": int(ram_match.group(1)) if ram_match else None,
        "storage_gb_min": int(storage_match.group(1)) if storage_match else None,
        "storage_type": "ssd" if storage_match or "ssd" in lowered else None,
    }
    if specs["ram_gb_min"] is None or specs["storage_gb_min"] is None or specs["storage_type"] is None:
        ambiguities.append("RAM and SSD size must be numbers, not a description of performance.")

    forbidden = []
    if "no warranty" in lowered or "without warranty" in lowered:
        forbidden.append("warranty")
    if "no accessories" in lowered or "no accessory" in lowered:
        forbidden.append("accessory")
    forbidden.append("software")

    approval_required = "approve" in lowered
    if maximum is None and not any("amount" in item or "around" in item for item in ambiguities):
        ambiguities.append("No hard maximum was found. State a total in dollars.")

    payload = {
        "currency": "USD",
        "maximum_total_minor": maximum or 0,
        "amount_includes": ["item", "tax", "shipping"],
        "allowed_brands": allowed or ["unspecified"],
        "required_specs": {
            "ram_gb_min": specs["ram_gb_min"] or 0,
            "storage_gb_min": specs["storage_gb_min"] or 0,
            "storage_type": specs["storage_type"] or "unspecified",
        },
        "forbidden_addon_types": forbidden,
        "max_executions": 1,
        "approval_required": approval_required,
        "preferences": preferences,
        "ambiguities": ambiguities,
        "original_instruction": instruction.strip(),
        "stated_maximum_minor": stated,
    }
    if ambiguities or maximum is None or not allowed or specs["ram_gb_min"] is None:
        payload["activatable"] = False
        return payload
    checked = accept_compiler_payload(payload)
    checked["activatable"] = True
    checked["stated_maximum_minor"] = stated
    return checked


def check_model_draft(instruction: str, raw: dict) -> dict:
    """A model may propose a draft. It may not hide a vague phrase or set status."""

    scripted = compile_scripted(instruction)
    if not isinstance(raw, dict):
        raise EngineError("compiler_invalid", "Compiler output was not an object.", 400)
    if "status" in raw:
        raise EngineError("compiler_overreach", "The compiler cannot set policy status.", 409)
    if scripted["ambiguities"] and not raw.get("ambiguities"):
        raise EngineError("compiler_overreach", "The model treated a vague phrase as a hard rule.", 409)
    accepted = accept_compiler_payload(raw)
    if scripted["activatable"]:
        same = (
            accepted["maximum_total_minor"] == scripted["maximum_total_minor"]
            and list(accepted["allowed_brands"]) == list(scripted["allowed_brands"])
            and accepted["required_specs"] == scripted["required_specs"]
            and bool(accepted["approval_required"]) == bool(scripted["approval_required"])
        )
        if not same:
            raise EngineError(
                "compiler_invalid",
                "The model draft disagreed with the hard numbers in the instruction.",
                400,
            )
    accepted["activatable"] = not accepted["ambiguities"]
    accepted["stated_maximum_minor"] = scripted["stated_maximum_minor"]
    return accepted
