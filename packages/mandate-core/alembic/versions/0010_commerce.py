"""Transactions, budget reservations, payment attempts, and provider accounts."""

from alembic import op

revision = "0010_commerce"
down_revision = "0009_approvals"
branch_labels = None
depends_on = None


UPGRADE = """
create schema if not exists integrations;

create table commerce.transactions (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  proposal_id uuid not null references commerce.carts (id),
  approval_id uuid not null unique references approvals.approvals (id),
  policy_version_id uuid not null references policies.policy_versions (id),
  cart_hash text not null,
  amount_minor bigint not null check (amount_minor >= 0),
  currency char(3) not null references commerce.currencies (code),
  status text not null check (status in (
    'prepared', 'reserved', 'authorized', 'captured', 'voided', 'refunded', 'failed', 'unknown'
  )),
  provider text not null,
  provider_order_id text,
  provider_authorization_id text,
  provider_capture_id text,
  reason_code text not null default '',
  idempotency_key text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, idempotency_key)
);

create index transactions_by_order
  on commerce.transactions (provider, provider_order_id);

create table commerce.budget_reservations (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  policy_version_id uuid not null references policies.policy_versions (id),
  transaction_id uuid not null unique references commerce.transactions (id),
  amount_minor bigint not null check (amount_minor >= 0),
  status text not null check (status in ('held', 'captured', 'released')),
  created_at timestamptz not null default now()
);

create index reservations_by_policy
  on commerce.budget_reservations (organization_id, policy_version_id, status);

create table commerce.payment_attempts (
  id uuid primary key default uuidv7(),
  transaction_id uuid not null references commerce.transactions (id),
  operation text not null check (operation in ('create', 'authorize', 'capture', 'void', 'refund', 'retrieve')),
  request_id text not null,
  provider_status text,
  raw_response jsonb,
  created_at timestamptz not null default now(),
  unique (transaction_id, operation, request_id)
);

create table integrations.provider_accounts (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  provider text not null,
  mode text not null check (mode in ('sandbox', 'live')) default 'sandbox',
  merchant_id text,
  created_at timestamptz not null default now(),
  unique (organization_id, provider)
);

create table integrations.webhook_deliveries (
  id uuid primary key default uuidv7(),
  provider text not null,
  event_id text not null,
  event_type text not null,
  verified boolean not null default false,
  received_at timestamptz not null default now(),
  raw jsonb,
  unique (provider, event_id)
);

alter table commerce.transactions enable row level security;
alter table commerce.transactions force row level security;
create policy tenant_isolation on commerce.transactions
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table commerce.budget_reservations enable row level security;
alter table commerce.budget_reservations force row level security;
create policy tenant_isolation on commerce.budget_reservations
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table integrations.provider_accounts enable row level security;
alter table integrations.provider_accounts force row level security;
create policy tenant_isolation on integrations.provider_accounts
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

-- The outbox worker publishes across tenants. It sets app.worker = 'on', a flag
-- only the worker process ever sets; a tenant request never does. This policy is
-- OR'd with tenant_isolation, so normal requests are unaffected.
create policy worker_publish on events.outbox
  for all
  using (current_setting('app.worker', true) = 'on')
  with check (current_setting('app.worker', true) = 'on');

grant usage on schema integrations to mandate_app;
grant select, insert, update on commerce.transactions to mandate_app;
grant select, insert, update on commerce.budget_reservations to mandate_app;
grant select, insert on commerce.payment_attempts to mandate_app;
grant select, insert, update on approvals.approvals to mandate_app;
grant select, insert, update on integrations.provider_accounts to mandate_app;
grant select, insert on integrations.webhook_deliveries to mandate_app;
"""

DOWNGRADE = """
drop policy if exists worker_publish on events.outbox;
drop table if exists integrations.webhook_deliveries;
drop table if exists integrations.provider_accounts;
drop table if exists commerce.payment_attempts;
drop table if exists commerce.budget_reservations;
drop table if exists commerce.transactions;
drop schema if exists integrations;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
