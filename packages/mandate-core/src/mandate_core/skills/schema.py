"""Check skill arguments against the registered JSON schema subset."""

from mandate_core.errors import EngineError


def arguments_match(schema: dict, arguments: dict) -> None:
    if schema.get("type") not in (None, "object"):
        raise EngineError("skill_invalid", "This skill schema is not an object.", 400)
    if not isinstance(arguments, dict):
        raise EngineError("skill_invalid", "Skill arguments must be an object.", 400)
    properties = schema.get("properties") or {}
    if schema.get("additionalProperties") is False:
        extra = [name for name in arguments if name not in properties]
        if extra:
            raise EngineError("skill_invalid", "Unexpected argument " + extra[0] + ".", 400)
    for name in schema.get("required") or []:
        if name not in arguments:
            raise EngineError("skill_invalid", "Missing argument " + name + ".", 400)
    for name, spec in properties.items():
        if name not in arguments:
            continue
        if spec.get("type") == "string" and not isinstance(arguments[name], str):
            raise EngineError("skill_invalid", name + " must be a string.", 400)
