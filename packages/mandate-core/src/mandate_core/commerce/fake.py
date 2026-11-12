"""A deterministic payment provider for tests. Not registered in a live process.

It mimics a provider that supports separate authorization and capture (like
PayPal Orders v2 with intent AUTHORIZE), so the commerce state machine can be
exercised end to end without a network or sandbox credentials.
"""

from mandate_core.commerce.provider import (
    AuthorizeOrder,
    CaptureOrder,
    CreateOrder,
    ProviderCapabilities,
    ProviderEvent,
    ProviderResult,
    RefundOrder,
    VoidOrder,
)


class FakeProvider:
    name = "fake"

    def __init__(self, fail_on: set[str] | None = None, timeout_on: set[str] | None = None):
        self.fail_on = fail_on or set()
        self.timeout_on = timeout_on or set()
        self.calls: list[str] = []

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(separate_authorization=True, refunds=True)

    def _guard(self, operation: str) -> None:
        self.calls.append(operation)
        if operation in self.timeout_on:
            raise TimeoutError(f"fake provider timed out on {operation}")
        if operation in self.fail_on:
            raise RuntimeError(f"fake provider refused {operation}")

    async def create_order(self, command: CreateOrder) -> ProviderResult:
        self._guard("create")
        return ProviderResult(status="CREATED", provider_order_id=f"ORDER-{command.transaction_id}", raw={"id": f"ORDER-{command.transaction_id}", "status": "CREATED"})

    async def authorize(self, command: AuthorizeOrder) -> ProviderResult:
        self._guard("authorize")
        return ProviderResult(
            status="AUTHORIZED",
            provider_order_id=command.provider_order_id,
            provider_authorization_id=f"AUTH-{command.transaction_id}",
            raw={"status": "AUTHORIZED"},
        )

    async def capture(self, command: CaptureOrder) -> ProviderResult:
        self._guard("capture")
        return ProviderResult(
            status="COMPLETED",
            provider_order_id=command.provider_order_id,
            provider_authorization_id=command.provider_authorization_id,
            provider_capture_id=f"CAP-{command.transaction_id}",
            raw={"status": "COMPLETED"},
        )

    async def void(self, command: VoidOrder) -> ProviderResult:
        self._guard("void")
        return ProviderResult(status="VOIDED", provider_order_id=command.provider_order_id, raw={"status": "VOIDED"})

    async def refund(self, command: RefundOrder) -> ProviderResult:
        self._guard("refund")
        return ProviderResult(status="REFUNDED", provider_capture_id=command.provider_capture_id, raw={"status": "REFUNDED"})

    async def verify_webhook(self, headers: dict, body: bytes) -> ProviderEvent:
        return ProviderEvent(event_id=headers.get("event-id", "evt-fake"), event_type=headers.get("event-type", "TEST"), provider_order_id=None, verified=True, raw={})
