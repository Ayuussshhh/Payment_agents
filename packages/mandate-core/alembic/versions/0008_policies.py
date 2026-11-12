"""Policy versions, evaluations, and the one-active-version rule."""

from alembic import op

revision = "0008_policies"
down_revision = "0007_agent_lock"
branch_labels = None
depends_on = None


UPGRADE = """
create schema if not exists policies;

create table policies.policies (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  name text not null,
  created_at timestamptz not null default now()
);

create table policies.policy_versions (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  policy_id uuid not null references policies.policies (id),
  version integer not null check (version >= 1),
  status text not null check (status in ('draft', 'active', 'retired')),
  currency char(3) not null,
  maximum_total_minor bigint not null check (maximum_total_minor > 0),
  constraints jsonb not null,
  original_instruction text not null,
  ambiguities jsonb not null default '[]',
  preferences jsonb not null default '[]',
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  activated_at timestamptz,
  unique (policy_id, version)
);

create unique index one_active_policy_version
  on policies.policy_versions (organization_id, policy_id)
  where status = 'active';

create table policies.evaluations (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  policy_version_id uuid not null references policies.policy_versions (id),
  proposal_id uuid not null,
  decision text not null check (decision in ('allow', 'deny', 'needs_approval')),
  reason_code text not null,
  cart_hash text,
  evaluated_amount_minor bigint,
  result jsonb not null,
  created_at timestamptz not null default now()
);

create index evaluations_recent
  on policies.evaluations (organization_id, policy_version_id, created_at desc);

create table policies.idempotency_keys (
  organization_id uuid not null references identity.organizations (id),
  scope text not null,
  key text not null,
  request_hash text not null,
  resource_id uuid not null references policies.policy_versions (id),
  primary key (organization_id, scope, key)
);

create or replace function policies.prevent_version_edit() returns trigger
language plpgsql
as $$
begin
  if new.currency is distinct from old.currency
     or new.maximum_total_minor is distinct from old.maximum_total_minor
     or new.constraints is distinct from old.constraints
     or new.original_instruction is distinct from old.original_instruction
     or new.ambiguities is distinct from old.ambiguities
     or new.preferences is distinct from old.preferences
     or new.expires_at is distinct from old.expires_at
     or new.version is distinct from old.version
     or new.policy_id is distinct from old.policy_id
     or new.organization_id is distinct from old.organization_id
     or new.created_at is distinct from old.created_at
  then
    raise exception 'policy version is immutable' using errcode = '23514';
  end if;
  if new.status is distinct from old.status and not (
       (old.status = 'draft' and new.status = 'active')
       or (old.status = 'active' and new.status = 'retired')
     )
  then
    raise exception 'policy status cannot change that way' using errcode = '23514';
  end if;
  if new.status = 'active' and jsonb_typeof(new.ambiguities) = 'array' and jsonb_array_length(new.ambiguities) > 0 then
    raise exception 'policy ambiguities block activation' using errcode = '23514';
  end if;
  return new;
end
$$;

create trigger policy_versions_immutable
  before update on policies.policy_versions
  for each row execute function policies.prevent_version_edit();

alter table policies.policies enable row level security;
alter table policies.policies force row level security;
create policy tenant_isolation on policies.policies
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table policies.policy_versions enable row level security;
alter table policies.policy_versions force row level security;
create policy tenant_isolation on policies.policy_versions
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table policies.evaluations enable row level security;
alter table policies.evaluations force row level security;
create policy tenant_isolation on policies.evaluations
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table policies.idempotency_keys enable row level security;
alter table policies.idempotency_keys force row level security;
create policy tenant_isolation on policies.idempotency_keys
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

grant usage on schema policies to mandate_app;
grant select, insert, update on policies.policies to mandate_app;
grant select, insert, update on policies.policy_versions to mandate_app;
grant select, insert on policies.evaluations to mandate_app;
grant select, insert on policies.idempotency_keys to mandate_app;
"""

DOWNGRADE = """
drop table if exists policies.idempotency_keys;
drop table if exists policies.evaluations;
drop table if exists policies.policy_versions;
drop function if exists policies.prevent_version_edit();
drop table if exists policies.policies;
drop schema if exists policies;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
