"""Minor units stay integers. A decimal string exists only for a provider boundary."""

from mandate_core.errors import EngineError

ENABLED_CURRENCIES = frozenset({"USD"})
USD_EXPONENT = 2


def minor_to_decimal(minor: int, exponent: int = USD_EXPONENT) -> str:
    if isinstance(minor, bool) or not isinstance(minor, int):
        raise EngineError("amount", "An amount must be an integer number of minor units.", 400)
    if minor < 0:
        raise EngineError("amount", "An amount cannot be negative.", 400)
    scale = 10 ** exponent
    whole, fraction = divmod(minor, scale)
    return f"{whole}.{fraction:0{exponent}d}"
