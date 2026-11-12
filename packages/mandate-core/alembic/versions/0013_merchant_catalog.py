"""Workspace-owned catalog items and immutable item revisions."""

from alembic import op

revision = "0013_merchant_catalog"
down_revision = "0012_approval_url"
branch_labels = None
depends_on = None


UPGRADE = """
create schema if not exists merchant;

create table merchant.catalog_items (
  organization_id uuid not null references identity.organizations (id),
  sku text not null,
  name text not null,
  brand text not null,
  category text not null default '',
  description text not null default '',
  currency char(3) not null default 'USD' references commerce.currencies (code),
  unit_amount_minor bigint not null check (unit_amount_minor > 0),
  ram_gb integer check (ram_gb is null or ram_gb > 0),
  storage_gb integer check (storage_gb is null or storage_gb > 0),
  storage_type text,
  source_url text,
  active boolean not null default true,
  version integer not null default 1 check (version >= 1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (organization_id, sku)
);

insert into commerce.currencies (code, exponent, enabled)
values ('INR', 2, true), ('EUR', 2, true), ('GBP', 2, true)
on conflict (code) do nothing;

create table merchant.catalog_item_versions (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  sku text not null,
  version integer not null check (version >= 1),
  snapshot jsonb not null,
  changed_by uuid references auth."user" (id),
  created_at timestamptz not null default now(),
  unique (organization_id, sku, version),
  foreign key (organization_id, sku) references merchant.catalog_items (organization_id, sku)
);

alter table merchant.catalog_items enable row level security;
alter table merchant.catalog_items force row level security;
create policy tenant_isolation on merchant.catalog_items
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table merchant.catalog_item_versions enable row level security;
alter table merchant.catalog_item_versions force row level security;
create policy tenant_isolation on merchant.catalog_item_versions
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

grant usage on schema merchant to mandate_app;
grant select, insert, update on merchant.catalog_items to mandate_app;
grant select, insert on merchant.catalog_item_versions to mandate_app;
"""


DOWNGRADE = """
drop table if exists merchant.catalog_item_versions;
drop table if exists merchant.catalog_items;
drop schema if exists merchant;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
