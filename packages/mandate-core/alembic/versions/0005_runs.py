"""Run rows and immutable skill names on a published version."""

from alembic import op

revision = "0005_runs"
down_revision = "0004_usage"
branch_labels = None
depends_on = None


UPGRADE = """
alter table agents.agent_versions
  add column skill_names jsonb not null default '[]';

create or replace function agents.prevent_version_edit() returns trigger
language plpgsql
as $$
begin
  if new.provider is distinct from old.provider
     or new.model is distinct from old.model
     or new.temperature is distinct from old.temperature
     or new.fallbacks is distinct from old.fallbacks
     or new.system_prompt is distinct from old.system_prompt
     or new.skill_names is distinct from old.skill_names
  then
    raise exception 'agent version is immutable' using errcode = '23514';
  end if;
  return new;
end
$$;

create table agents.agent_runs (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  agent_version_id uuid not null references agents.agent_versions (id),
  policy_version_id uuid,
  status text not null check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'limited')),
  cancel_requested boolean not null default false,
  input jsonb not null,
  output jsonb not null default '{}',
  stop_reason text not null default '',
  created_at timestamptz not null default now(),
  finished_at timestamptz
);

grant select, insert, update on agents.agent_runs to mandate_app;

alter table agents.agent_runs enable row level security;
alter table agents.agent_runs force row level security;
create policy tenant_isolation on agents.agent_runs
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());
"""

DOWNGRADE = """
drop table if exists agents.agent_runs;
alter table agents.agent_versions drop column if exists skill_names;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
