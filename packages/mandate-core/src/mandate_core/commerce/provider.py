"""The payment provider boundary. Commerce talks to this, never to an SDK.

Every adapter — PayPal sandbox, the fake used in tests, a future provider —
implements this one Protocol. The commerce engine decides what to charge; the
adapter only carries the request to the provider and reports what it said.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ProviderCapabilities:
    """What a provider can do. Commerce refuses a policy a provider cannot honor,
    rather than emulating it (e.g. capturing early to fake a delayed capture)."""

    separate_authorization: bool
    refunds: bool


@dataclass(frozen=True)
class CreateOrder:
    transaction_id: str
    amount_minor: int
    currency: str
    merchant_id: str
    catalog_sku: str


@dataclass(frozen=True)
class AuthorizeOrder:
    transaction_id: str
    provider_order_id: str


@dataclass(frozen=True)
class CaptureOrder:
    transaction_id: str
    provider_order_id: str
    provider_authorization_id: str


@dataclass(frozen=True)
class VoidOrder:
    transaction_id: str
    provider_order_id: str
    provider_authorization_id: str | None


@dataclass(frozen=True)
class RefundOrder:
    transaction_id: str
    provider_capture_id: str
    amount_minor: int
    currency: str


@dataclass(frozen=True)
class ProviderResult:
    """One provider response: the ids it returned, its status, and the raw body
    (secrets redacted) that we keep as evidence in payment_attempts."""

    status: str
    provider_order_id: str | None = None
    provider_authorization_id: str | None = None
    provider_capture_id: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderEvent:
    """A verified webhook. An unverified body never becomes one of these."""

    event_id: str
    event_type: str
    provider_order_id: str | None
    verified: bool
    raw: dict = field(default_factory=dict)


class PaymentProvider(Protocol):
    name: str

    def capabilities(self) -> ProviderCapabilities: ...

    async def create_order(self, command: CreateOrder) -> ProviderResult: ...

    async def authorize(self, command: AuthorizeOrder) -> ProviderResult: ...

    async def capture(self, command: CaptureOrder) -> ProviderResult: ...

    async def void(self, command: VoidOrder) -> ProviderResult: ...

    async def refund(self, command: RefundOrder) -> ProviderResult: ...

    async def verify_webhook(self, headers: dict, body: bytes) -> ProviderEvent: ...
