"""Token usage rows. The application role can insert and select them."""

from alembic import op

revision = "0004_usage"
down_revision = "0003_contracts"
branch_labels = None
depends_on = None


UPGRADE = """
create schema if not exists usage;

create table usage.token_usage (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  run_id uuid,
  provider text not null,
  model text not null,
  input_tokens integer not null check (input_tokens >= 0),
  output_tokens integer not null check (output_tokens >= 0),
  occurred_at timestamptz not null default now()
);

grant usage on schema usage to mandate_app;
grant select, insert on usage.token_usage to mandate_app;

alter table usage.token_usage enable row level security;
alter table usage.token_usage force row level security;
create policy tenant_isolation on usage.token_usage
  using (organization_id = events.tenant_id())
  with check (organization_id = events.tenant_id());
"""

DOWNGRADE = """
drop table if exists usage.token_usage;
drop schema if exists usage;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
