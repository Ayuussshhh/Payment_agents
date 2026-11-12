"""Carts a decision can bind, and the approval row for one of those carts."""

from alembic import op

revision = "0009_approvals"
down_revision = "0008_policies"
branch_labels = None
depends_on = None


UPGRADE = """
create schema if not exists commerce;
create schema if not exists approvals;

create table commerce.currencies (
  code char(3) primary key,
  exponent smallint not null check (exponent >= 0 and exponent <= 4),
  enabled boolean not null default false
);

insert into commerce.currencies (code, exponent, enabled) values ('USD', 2, true);

create table commerce.carts (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  policy_version_id uuid not null references policies.policy_versions (id),
  run_id uuid references agents.agent_runs (id),
  seller_id text not null,
  currency char(3) not null references commerce.currencies (code),
  total_minor bigint not null check (total_minor >= 0),
  cart_hash text not null,
  hash_version integer not null,
  catalog_sku text not null,
  created_at timestamptz not null default now()
);

create table commerce.cart_items (
  id uuid primary key default uuidv7(),
  cart_id uuid not null references commerce.carts (id),
  sku text not null,
  brand text not null,
  quantity integer not null check (quantity >= 1),
  unit_amount_minor bigint not null check (unit_amount_minor >= 0),
  addon_type text,
  ram_gb integer,
  storage_gb integer,
  storage_type text
);

create table approvals.approvals (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  proposal_id uuid not null references commerce.carts (id),
  policy_version_id uuid not null references policies.policy_versions (id),
  agent_version_id uuid references agents.agent_versions (id),
  approver_user_id text,
  cart_hash text not null,
  hash_version integer not null,
  amount_minor bigint not null,
  currency char(3) not null,
  merchant_id text not null,
  status text not null check (status in ('pending', 'valid', 'rejected', 'expired', 'revoked', 'consumed')),
  snapshot jsonb not null,
  signature text,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique (organization_id, proposal_id)
);

create index approvals_inbox
  on approvals.approvals (organization_id, status, expires_at);

create table approvals.idempotency_keys (
  organization_id uuid not null references identity.organizations (id),
  scope text not null,
  key text not null,
  request_hash text not null,
  resource_id uuid not null references approvals.approvals (id),
  primary key (organization_id, scope, key)
);

alter table commerce.carts enable row level security;
alter table commerce.carts force row level security;
create policy tenant_isolation on commerce.carts
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table approvals.approvals enable row level security;
alter table approvals.approvals force row level security;
create policy tenant_isolation on approvals.approvals
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table approvals.idempotency_keys enable row level security;
alter table approvals.idempotency_keys force row level security;
create policy tenant_isolation on approvals.idempotency_keys
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

grant usage on schema commerce, approvals to mandate_app;
grant select on commerce.currencies to mandate_app;
grant select, insert on commerce.carts, commerce.cart_items to mandate_app;
grant select, insert, update on approvals.approvals to mandate_app;
grant select, insert on approvals.idempotency_keys to mandate_app;
"""

DOWNGRADE = """
drop table if exists approvals.idempotency_keys;
drop table if exists approvals.approvals;
drop table if exists commerce.cart_items;
drop table if exists commerce.carts;
drop table if exists commerce.currencies;
drop schema if exists approvals;
drop schema if exists commerce;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
