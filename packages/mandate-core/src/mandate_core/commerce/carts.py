"""Persist the cart a decision judged. A later price edit is a different cart."""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.contracts import Proposal
from mandate_core.contracts.models import CartLine, Seller
from mandate_core.errors import EngineError
from mandate_core.persistence.scope import use_tenant_scope
from mandate_core.policy.hashing import HASH_VERSION, canonical_hash

_INSERT_CART = text(
    """
    insert into commerce.carts (
      id, organization_id, policy_version_id, run_id, seller_id, currency,
      total_minor, cart_hash, hash_version, catalog_sku
    )
    values (
      :id, :organization_id, :policy_version_id, :run_id, :seller_id, :currency,
      :total_minor, :cart_hash, :hash_version, :catalog_sku
    )
    """
)

_INSERT_ITEM = text(
    """
    insert into commerce.cart_items (
      id, cart_id, sku, brand, quantity, unit_amount_minor, addon_type, ram_gb, storage_gb, storage_type
    )
    values (
      :id, :cart_id, :sku, :brand, :quantity, :unit_amount_minor, :addon_type, :ram_gb, :storage_gb, :storage_type
    )
    """
)

_CART = text(
    """
    select c.id, c.organization_id, c.policy_version_id, c.seller_id, c.currency, c.total_minor,
           c.cart_hash, c.hash_version, c.catalog_sku, v.policy_id, v.version, v.status as policy_status
    from commerce.carts c
    join policies.policy_versions v on v.id = c.policy_version_id
    where c.organization_id = :organization_id and c.id = :cart_id
    """
)

_ITEMS = text(
    """
    select sku, brand, quantity, unit_amount_minor, addon_type, ram_gb, storage_gb, storage_type
    from commerce.cart_items
    where cart_id = :cart_id
    order by sku, addon_type nulls first
    """
)


def store_cart(connection: Connection, organization_id: UUID, policy_version_id: UUID, proposal: Proposal, cart_hash: str, run_id: UUID | None, catalog_sku: str) -> UUID:
    cart_id = uuid4()
    connection.execute(
        _INSERT_CART,
        {
            "id": cart_id,
            "organization_id": organization_id,
            "policy_version_id": policy_version_id,
            "run_id": run_id,
            "seller_id": proposal.seller.id,
            "currency": proposal.currency,
            "total_minor": proposal.total_minor,
            "cart_hash": cart_hash,
            "hash_version": HASH_VERSION,
            "catalog_sku": catalog_sku,
        },
    )
    for line in proposal.lines:
        connection.execute(
            _INSERT_ITEM,
            {
                "id": uuid4(),
                "cart_id": cart_id,
                "sku": line.sku,
                "brand": line.brand,
                "quantity": line.quantity,
                "unit_amount_minor": line.unit_amount_minor,
                "addon_type": line.addon_type,
                "ram_gb": line.ram_gb,
                "storage_gb": line.storage_gb,
                "storage_type": line.storage_type,
            },
        )
    return cart_id


def load_cart(connection: Connection, organization_id: UUID, cart_id: UUID) -> tuple[Proposal, dict]:
    use_tenant_scope(connection, organization_id)
    row = connection.execute(_CART, {"organization_id": organization_id, "cart_id": cart_id}).mappings().first()
    if row is None:
        raise EngineError("not_found", "That proposal does not exist.", 404)
    items = connection.execute(_ITEMS, {"cart_id": cart_id}).mappings().all()
    lines = tuple(
        CartLine(
            sku=item["sku"],
            brand=item["brand"],
            quantity=item["quantity"],
            unit_amount_minor=item["unit_amount_minor"],
            addon_type=item["addon_type"],
            ram_gb=item["ram_gb"],
            storage_gb=item["storage_gb"],
            storage_type=item["storage_type"],
        )
        for item in items
    )
    proposal = Proposal(
        currency=str(row["currency"]).strip(),
        mandate_id=row["policy_id"],
        mandate_version=row["version"],
        seller=Seller(id=row["seller_id"]),
        lines=lines,
        total_minor=row["total_minor"],
    )
    meta = {
        "policy_version_id": row["policy_version_id"],
        "policy_status": row["policy_status"],
        "policy_version": row["version"],
        "stored_hash": row["cart_hash"],
        "hash_version": row["hash_version"],
        "seller_id": row["seller_id"],
        "catalog_sku": row["catalog_sku"],
    }
    return proposal, meta


def current_hash(connection: Connection, organization_id: UUID, cart_id: UUID) -> tuple[Proposal, dict, str]:
    proposal, meta = load_cart(connection, organization_id, cart_id)
    return proposal, meta, canonical_hash(proposal)
