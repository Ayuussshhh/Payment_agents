"""Tenant-scoped merchant catalog with immutable item revision snapshots."""

import json
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.contracts.context import ExecutionContext
from mandate_core.errors import EngineError
from mandate_core.identity.authorize import authorize_action
from mandate_core.persistence.scope import use_tenant_scope

_FIELDS = ("name", "brand", "category", "description", "currency", "unit_amount_minor", "ram_gb", "storage_gb", "storage_type", "source_url")
_SELECT_FIELDS = "sku, name, brand, category, description, currency, unit_amount_minor, ram_gb, storage_gb, storage_type, source_url, active, version, created_at, updated_at"


def list_catalog(connection: Connection, context: ExecutionContext, *, include_archived: bool = False) -> list[dict]:
    authorize_action(context, "read", "CatalogItem")
    use_tenant_scope(connection, context.organization_id)
    rows = connection.execute(
        text(f"select {_SELECT_FIELDS} from merchant.catalog_items where organization_id = :organization_id and (:include_archived or active) order by updated_at desc, sku"),
        {"organization_id": context.organization_id, "include_archived": include_archived},
    ).mappings().all()
    return [_plain(dict(row)) for row in rows]


def get_catalog_item(connection: Connection, organization_id, sku: str) -> dict | None:
    row = connection.execute(
        text(f"select {_SELECT_FIELDS} from merchant.catalog_items where organization_id = :organization_id and sku = :sku and active"),
        {"organization_id": organization_id, "sku": sku.strip().upper()},
    ).mappings().first()
    return _plain(dict(row)) if row else None


def save_catalog_item(connection: Connection, context: ExecutionContext, sku: str, data: dict) -> dict:
    use_tenant_scope(connection, context.organization_id)
    normalized_sku = sku.strip().upper()
    if not normalized_sku or len(normalized_sku) > 80:
        raise EngineError("catalog_invalid", "SKU must be between 1 and 80 characters.", 400)
    row = connection.execute(
        text("select version from merchant.catalog_items where organization_id = :organization_id and sku = :sku for update"),
        {"organization_id": context.organization_id, "sku": normalized_sku},
    ).first()
    authorize_action(context, "update" if row else "create", "CatalogItem")
    next_version = int(row[0]) + 1 if row else 1
    params = {"organization_id": context.organization_id, "sku": normalized_sku, "version": next_version}
    params.update({field: data.get(field) for field in _FIELDS})
    if row:
        connection.execute(
            text("""update merchant.catalog_items set name=:name, brand=:brand, category=:category,
                description=:description, currency=:currency, unit_amount_minor=:unit_amount_minor,
                ram_gb=:ram_gb, storage_gb=:storage_gb, storage_type=:storage_type, source_url=:source_url,
                active=true, version=:version, updated_at=now()
                where organization_id=:organization_id and sku=:sku"""), params,
        )
    else:
        connection.execute(
            text("""insert into merchant.catalog_items
                (organization_id, sku, name, brand, category, description, currency, unit_amount_minor,
                 ram_gb, storage_gb, storage_type, source_url, version)
                values (:organization_id, :sku, :name, :brand, :category, :description, :currency,
                        :unit_amount_minor, :ram_gb, :storage_gb, :storage_type, :source_url, :version)"""), params,
        )
    snapshot = {key: params[key] for key in ("sku", *_FIELDS)}
    connection.execute(
        text("""insert into merchant.catalog_item_versions
            (id, organization_id, sku, version, snapshot, changed_by)
            values (:id, :organization_id, :sku, :version, cast(:snapshot as jsonb), :changed_by)"""),
        {"id": uuid4(), "organization_id": context.organization_id, "sku": normalized_sku,
         "version": next_version, "snapshot": json.dumps(snapshot), "changed_by": context.user_id},
    )
    return get_catalog_item(connection, context.organization_id, normalized_sku)


def archive_catalog_item(connection: Connection, context: ExecutionContext, sku: str) -> dict:
    use_tenant_scope(connection, context.organization_id)
    normalized_sku = sku.strip().upper()
    row = connection.execute(
        text(f"select {_SELECT_FIELDS} from merchant.catalog_items where organization_id=:organization_id and sku=:sku and active for update"),
        {"organization_id": context.organization_id, "sku": normalized_sku},
    ).mappings().first()
    if row is None:
        raise EngineError("not_found", "That catalog item does not exist.", 404)
    authorize_action(context, "update", "CatalogItem")
    next_version = int(row["version"]) + 1
    connection.execute(
        text("update merchant.catalog_items set active=false, version=:version, updated_at=now() where organization_id=:organization_id and sku=:sku"),
        {"organization_id": context.organization_id, "sku": normalized_sku, "version": next_version},
    )
    snapshot = dict(row)
    snapshot.update({"sku": normalized_sku, "version": next_version, "active": False})
    connection.execute(
        text("""insert into merchant.catalog_item_versions
            (id, organization_id, sku, version, snapshot, changed_by)
            values (:id, :organization_id, :sku, :version, cast(:snapshot as jsonb), :changed_by)"""),
        {"id": uuid4(), "organization_id": context.organization_id, "sku": normalized_sku,
         "version": next_version, "snapshot": json.dumps(_snapshot_plain(snapshot)), "changed_by": context.user_id},
    )
    return {"sku": normalized_sku, "active": False, "version": next_version}


def catalog_history(connection: Connection, context: ExecutionContext, sku: str) -> list[dict]:
    authorize_action(context, "read", "CatalogItem")
    use_tenant_scope(connection, context.organization_id)
    rows = connection.execute(
        text("select version, snapshot, changed_by, created_at from merchant.catalog_item_versions where organization_id=:organization_id and sku=:sku order by version desc"),
        {"organization_id": context.organization_id, "sku": sku.strip().upper()},
    ).mappings().all()
    return [{"version": row["version"], "snapshot": _json(row["snapshot"]),
             "changed_by": str(row["changed_by"]) if row["changed_by"] else None,
             "created_at": row["created_at"].isoformat() if row["created_at"] else None} for row in rows]


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def _plain(row: dict) -> dict:
    row["currency"] = str(row["currency"]).strip()
    for field in ("created_at", "updated_at"):
        if row.get(field):
            row[field] = row[field].isoformat()
    return row


def _snapshot_plain(row: dict) -> dict:
    result = dict(row)
    for field in ("currency",):
        if result.get(field) is not None:
            result[field] = str(result[field]).strip()
    for field in ("created_at", "updated_at"):
        if result.get(field) is not None:
            result[field] = result[field].isoformat()
    return result
