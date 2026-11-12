"""PayPal Orders v2 sandbox adapter. Live mode is refused, not emulated.

The commerce engine decides the amount and the transaction id; this adapter only
carries PayPal's REST calls and reports the ids and status it returns. The
transaction id is sent as PayPal-Request-Id so a retried create is idempotent at
the provider too. Credentials come from the environment, never from a database
row or an agent version.
"""

import base64
import os

import httpx

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
from mandate_core.errors import EngineError
from mandate_core.policy.money import minor_to_decimal

_SANDBOX = "https://api-m.sandbox.paypal.com"


def _env() -> str:
    return (os.environ.get("PAYPAL_ENV") or "sandbox").strip().lower()


class PayPalProvider:
    name = "paypal"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None, webhook_id: str | None = None, base_url: str | None = None, studio_url: str | None = None):
        if _env() == "live":
            raise EngineError("provider_live_refused", "PayPal live mode is refused in this release.", 400)
        self.client_id = client_id if client_id is not None else os.environ.get("PAYPAL_CLIENT_ID", "")
        self.client_secret = client_secret if client_secret is not None else os.environ.get("PAYPAL_CLIENT_SECRET", "")
        self.webhook_id = webhook_id if webhook_id is not None else os.environ.get("PAYPAL_WEBHOOK_ID", "")
        self.base_url = (base_url or _SANDBOX).rstrip("/")
        self.studio_url = (studio_url or os.environ.get("STUDIO_URL") or "http://localhost:3001").rstrip("/")

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(separate_authorization=True, refunds=True)

    def _require_credentials(self) -> None:
        if not self.client_id or not self.client_secret:
            raise EngineError("provider_unconfigured", "PayPal sandbox credentials are not set.", 503)

    async def _token(self, client: httpx.AsyncClient) -> str:
        self._require_credentials()
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        response = await client.post(
            f"{self.base_url}/v1/oauth2/token",
            headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
            content="grant_type=client_credentials",
        )
        if response.status_code >= 400:
            raise EngineError("provider_error", "PayPal rejected the credentials.", 502)
        return response.json().get("access_token", "")

    async def _post(self, path: str, token: str, body: dict | None, request_id: str, client: httpx.AsyncClient) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "PayPal-Request-Id": request_id}
        return await client.post(f"{self.base_url}{path}", headers=headers, json=body if body is not None else {})

    async def create_order(self, command: CreateOrder) -> ProviderResult:
        # No payee is sent: in sandbox the order settles to the credentialed
        # account. application_context carries the URLs PayPal redirects the buyer
        # to after they approve or cancel the order in the PayPal-hosted checkout.
        body = {
            "intent": "AUTHORIZE",
            "purchase_units": [
                {
                    "reference_id": command.catalog_sku,
                    "amount": {"currency_code": command.currency, "value": minor_to_decimal(command.amount_minor)},
                }
            ],
            "application_context": {
                "brand_name": "Mandate",
                "user_action": "CONTINUE",
                "shipping_preference": "NO_SHIPPING",
                "return_url": f"{self.studio_url}/checkout/return?tx={command.transaction_id}",
                "cancel_url": f"{self.studio_url}/checkout/cancel?tx={command.transaction_id}",
            },
        }
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._token(client)
            response = await self._post("/v2/checkout/orders", token, body, command.transaction_id, client)
        data = _json(response)
        if response.status_code >= 400:
            raise EngineError("provider_error", "PayPal refused the order.", 502)
        approval = next((link.get("href") for link in data.get("links", []) if link.get("rel") == "approve"), None)
        return ProviderResult(status=data.get("status", "CREATED"), provider_order_id=data.get("id"), approval_url=approval, raw=_redact(data))

    async def authorize(self, command: AuthorizeOrder) -> ProviderResult:
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._token(client)
            response = await self._post(f"/v2/checkout/orders/{command.provider_order_id}/authorize", token, None, command.transaction_id, client)
        data = _json(response)
        if response.status_code >= 400:
            raise EngineError("provider_error", "PayPal refused to authorize the order.", 502)
        authorization_id = _first_authorization_id(data)
        return ProviderResult(status=data.get("status", "AUTHORIZED"), provider_order_id=command.provider_order_id, provider_authorization_id=authorization_id, raw=_redact(data))

    async def capture(self, command: CaptureOrder) -> ProviderResult:
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._token(client)
            response = await self._post(f"/v2/payments/authorizations/{command.provider_authorization_id}/capture", token, None, command.transaction_id, client)
        data = _json(response)
        if response.status_code >= 400:
            raise EngineError("provider_error", "PayPal refused to capture the authorization.", 502)
        return ProviderResult(
            status=data.get("status", "COMPLETED"),
            provider_order_id=command.provider_order_id,
            provider_authorization_id=command.provider_authorization_id,
            provider_capture_id=data.get("id"),
            raw=_redact(data),
        )

    async def void(self, command: VoidOrder) -> ProviderResult:
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._token(client)
            response = await self._post(f"/v2/payments/authorizations/{command.provider_authorization_id}/void", token, None, command.transaction_id, client)
        if response.status_code >= 400:
            raise EngineError("provider_error", "PayPal refused to void the authorization.", 502)
        return ProviderResult(status="VOIDED", provider_order_id=command.provider_order_id, raw=_redact(_json(response)))

    async def refund(self, command: RefundOrder) -> ProviderResult:
        body = {"amount": {"currency_code": command.currency, "value": minor_to_decimal(command.amount_minor)}}
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._token(client)
            response = await self._post(f"/v2/payments/captures/{command.provider_capture_id}/refund", token, body, command.transaction_id, client)
        data = _json(response)
        if response.status_code >= 400:
            raise EngineError("provider_error", "PayPal refused the refund.", 502)
        return ProviderResult(status=data.get("status", "REFUNDED"), provider_capture_id=command.provider_capture_id, raw=_redact(data))

    async def verify_webhook(self, headers: dict, body: bytes) -> ProviderEvent:
        import json as _jsonlib

        lower = {key.lower(): value for key, value in headers.items()}
        try:
            event = _jsonlib.loads(body.decode() or "{}")
        except ValueError:
            return ProviderEvent(event_id="", event_type="", provider_order_id=None, verified=False)
        payload = {
            "auth_algo": lower.get("paypal-auth-algo"),
            "cert_url": lower.get("paypal-cert-url"),
            "transmission_id": lower.get("paypal-transmission-id"),
            "transmission_sig": lower.get("paypal-transmission-sig"),
            "transmission_time": lower.get("paypal-transmission-time"),
            "webhook_id": self.webhook_id,
            "webhook_event": event,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._token(client)
            response = await client.post(
                f"{self.base_url}/v1/notifications/verify-webhook-signature",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
        verified = response.status_code < 400 and _json(response).get("verification_status") == "SUCCESS"
        return ProviderEvent(
            event_id=str(event.get("id", "")),
            event_type=str(event.get("event_type", "")),
            provider_order_id=_resource_order_id(event),
            verified=bool(verified),
            raw=_redact(event),
        )


def _json(response: httpx.Response) -> dict:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _first_authorization_id(data: dict) -> str | None:
    for unit in data.get("purchase_units", []) or []:
        authorizations = (unit.get("payments") or {}).get("authorizations") or []
        if authorizations:
            return authorizations[0].get("id")
    return None


def _resource_order_id(event: dict) -> str | None:
    resource = event.get("resource") or {}
    return resource.get("id") or ((resource.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")


def _redact(data: dict) -> dict:
    """Keep the shape and ids, drop anything token-like. Evidence, not secrets."""
    redacted = {}
    for key, value in (data or {}).items():
        if key.lower() in {"access_token", "authorization", "client_secret"}:
            continue
        redacted[key] = value
    return redacted
