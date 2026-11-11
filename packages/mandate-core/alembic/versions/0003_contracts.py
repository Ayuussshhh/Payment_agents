"""Agent versions, the event spine, and organization row-level security."""

from alembic import op

revision = "0003_contracts"
down_revision = "0002_auth"
branch_labels = None
depends_on = None


UPGRADE = r"""
create schema if not exists agents;
create schema if not exists events;

create table agents.agents (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  name text not null,
  description text not null default '',
  graph_kind text not null check (graph_kind in ('compiler', 'buyer')),
  created_at timestamptz not null default now()
);

create table agents.agent_versions (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  agent_id uuid not null references agents.agents (id),
  version integer not null check (version >= 1),
  provider text not null,
  model text not null,
  temperature double precision not null default 0,
  fallbacks jsonb not null default '[]',
  system_prompt text not null,
  published_at timestamptz not null default now(),
  published_by uuid not null,
  unique (agent_id, version)
);

create function agents.prevent_version_edit() returns trigger
language plpgsql
as $$
begin
  if new.provider is distinct from old.provider
     or new.model is distinct from old.model
     or new.temperature is distinct from old.temperature
     or new.fallbacks is distinct from old.fallbacks
     or new.system_prompt is distinct from old.system_prompt
  then
    raise exception 'agent version is immutable' using errcode = '23514';
  end if;
  return new;
end
$$;

create trigger agent_versions_immutable
before update on agents.agent_versions
for each row execute function agents.prevent_version_edit();

create table events.outbox (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  name text not null,
  aggregate_type text not null,
  aggregate_id uuid not null,
  payload jsonb not null,
  occurred_at timestamptz not null,
  published_at timestamptz
);

create table events.audit_events (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  name text not null,
  aggregate_type text not null,
  aggregate_id uuid not null,
  actor_type text not null,
  actor_id text not null,
  request_id text not null,
  reason_code text not null default '',
  payload jsonb not null,
  occurred_at timestamptz not null default now()
);

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'mandate_app') then
    create role mandate_app;
  end if;
end
$$;

grant mandate_app to current_user;
grant usage on schema identity, agents, events, auth to mandate_app;
grant select on auth."user", auth.session to mandate_app;
grant select, insert on identity.organizations, identity.memberships, identity.role_bindings to mandate_app;
grant select, insert on agents.agents, agents.agent_versions to mandate_app;
grant select, insert on events.audit_events to mandate_app;
grant select, insert, update (published_at) on events.outbox to mandate_app;

create or replace function events.tenant_id() returns uuid
language sql
stable
as $$
  select nullif(current_setting('app.organization_id', true), '')::uuid
$$;

alter table identity.organizations enable row level security;
alter table identity.organizations force row level security;
create policy tenant_isolation on identity.organizations
  using (id = events.tenant_id())
  with check (id = events.tenant_id());

alter table identity.memberships enable row level security;
alter table identity.memberships force row level security;
create policy tenant_isolation on identity.memberships
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table identity.role_bindings enable row level security;
alter table identity.role_bindings force row level security;
create policy tenant_isolation on identity.role_bindings
  using (
    exists (
      select 1 from identity.memberships membership
      where membership.id = membership_id
        and membership.organization_id = events.tenant_id()
    )
  )
  with check (
    exists (
      select 1 from identity.memberships membership
      where membership.id = membership_id
        and membership.organization_id = events.tenant_id()
    )
  );

alter table agents.agents enable row level security;
alter table agents.agents force row level security;
create policy tenant_isolation on agents.agents
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table agents.agent_versions enable row level security;
alter table agents.agent_versions force row level security;
create policy tenant_isolation on agents.agent_versions
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table events.outbox enable row level security;
alter table events.outbox force row level security;
create policy tenant_isolation on events.outbox
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());

alter table events.audit_events enable row level security;
alter table events.audit_events force row level security;
create policy tenant_isolation on events.audit_events
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());
"""

DOWNGRADE = """
drop policy if exists tenant_isolation on events.audit_events;
drop policy if exists tenant_isolation on events.outbox;
drop policy if exists tenant_isolation on agents.agent_versions;
drop policy if exists tenant_isolation on agents.agents;
drop policy if exists tenant_isolation on identity.role_bindings;
drop policy if exists tenant_isolation on identity.memberships;
drop policy if exists tenant_isolation on identity.organizations;
drop function if exists events.tenant_id();
drop table if exists events.audit_events;
drop table if exists events.outbox;
drop table if exists agents.agent_versions;
drop function if exists agents.prevent_version_edit();
drop table if exists agents.agents;
drop schema if exists events;
drop schema if exists agents;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
