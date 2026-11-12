"""Canonical cart hash. Key order must not change the digest."""

import hashlib
import json

HASH_VERSION = 1


def _field(item, key):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key)


def canonical_body(proposal) -> dict:
    raw_lines = proposal["lines"] if isinstance(proposal, dict) else proposal.lines
    lines = []
    for line in raw_lines:
        lines.append(
            {
                "addon_type": _field(line, "addon_type"),
                "brand": _field(line, "brand"),
                "quantity": _field(line, "quantity"),
                "ram_gb": _field(line, "ram_gb"),
                "sku": _field(line, "sku"),
                "storage_gb": _field(line, "storage_gb"),
                "storage_type": _field(line, "storage_type"),
                "unit_amount_minor": _field(line, "unit_amount_minor"),
            }
        )
    lines.sort(key=lambda item: (item["sku"], "" if item["addon_type"] is None else item["addon_type"]))
    if isinstance(proposal, dict):
        seller = proposal["seller"]
        seller_id = seller["id"] if isinstance(seller, dict) else seller.id
        currency = proposal["currency"]
        mandate_id = proposal["mandate_id"]
        mandate_version = proposal["mandate_version"]
    else:
        seller_id = proposal.seller.id
        currency = proposal.currency
        mandate_id = proposal.mandate_id
        mandate_version = proposal.mandate_version
    return {
        "currency": currency,
        "hash_version": HASH_VERSION,
        "lines": lines,
        "mandate_id": str(mandate_id),
        "mandate_version": mandate_version,
        "seller_id": seller_id,
    }


def canonical_hash(proposal) -> str:
    encoded = json.dumps(canonical_body(proposal), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
