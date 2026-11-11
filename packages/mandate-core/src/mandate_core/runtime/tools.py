"""Tool definitions offered to a model. PayPal is never one of them."""

BLOCKED = {"paypal"}

PROPOSE_PARAMETERS = {
    "type": "object",
    "properties": {"sku": {"type": "string"}},
    "required": ["sku"],
    "additionalProperties": False,
}

LIST_PARAMETERS = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def tool_definitions(skill_names: tuple[str, ...]) -> tuple[dict, ...]:
    tools = []
    for name in skill_names:
        if name.lower() in BLOCKED:
            continue
        parameters = PROPOSE_PARAMETERS if name == "propose" else LIST_PARAMETERS
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": "A skill attached to this published version.",
                    "parameters": parameters,
                },
            }
        )
    return tuple(tools)
