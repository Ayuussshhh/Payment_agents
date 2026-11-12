"""Organization API keys for the developer platform. Secret stored as a hash."""

from alembic import op

revision = "0011_api_keys"
down_revision = "0010_commerce"
branch_labels = None
depends_on = None


# No row-level security: a key is resolved by prefix before the organization is
# known, the same way the Better Auth session table is read. Isolation is in the
# WHERE clause of every tenant-facing query, and the secret is only ever a hash.
UPGRADE = """
create table identity.api_keys (
  id uuid primary key default uuidv7(),
  organization_id uuid not null references identity.organizations (id),
  name text not null,
  prefix text not null,
  secret_hash text not null,
  created_by text not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

create unique index api_keys_prefix on identity.api_keys (prefix);
create index api_keys_by_org on identity.api_keys (organization_id, created_at desc);

grant select, insert, update on identity.api_keys to mandate_app;
"""

DOWNGRADE = """
drop table if exists identity.api_keys;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
