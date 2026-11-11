"""Identity tables. Auth tables and the user foreign key follow in the next revision."""

from alembic import op

revision = "0001_identity"
down_revision = None
branch_labels = None
depends_on = None


UPGRADE = """
do $$
begin
  if not exists (
    select 1
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where p.proname = 'uuidv7'
  ) then
    execute $fn$
      create function public.uuidv7() returns uuid
      language plpgsql
      volatile
      as $body$
      declare
        unix_ts_ms bytea;
        uuid_bytes bytea;
      begin
        unix_ts_ms := substring(int8send((extract(epoch from clock_timestamp()) * 1000)::bigint) from 3 for 6);
        uuid_bytes := uuid_send(gen_random_uuid());
        uuid_bytes := overlay(uuid_bytes placing unix_ts_ms from 1 for 6);
        uuid_bytes := set_byte(uuid_bytes, 6, (get_byte(uuid_bytes, 6) & 15) | 112);
        uuid_bytes := set_byte(uuid_bytes, 8, (get_byte(uuid_bytes, 8) & 63) | 128);
        return encode(uuid_bytes, 'hex')::uuid;
      end
      $body$
    $fn$;
  end if;
end
$$;

create schema if not exists identity;

create table identity.organizations (
  id uuid primary key default uuidv7(),
  name text not null,
  created_at timestamptz not null default now()
);

create table identity.memberships (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  user_id uuid not null,
  created_at timestamptz not null default now(),
  unique (organization_id, user_id)
);

create index memberships_user_id on identity.memberships (user_id);

create table identity.role_bindings (
  membership_id uuid not null references identity.memberships (id),
  role text not null check (role in ('owner', 'admin', 'developer', 'finance_manager', 'approver', 'viewer')),
  primary key (membership_id, role)
);
"""

DOWNGRADE = """
drop table if exists identity.role_bindings;
drop table if exists identity.memberships;
drop table if exists identity.organizations;
drop schema if exists identity;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
