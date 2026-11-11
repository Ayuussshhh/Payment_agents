"""Better Auth 1.7.20 tables in the auth schema, then the membership foreign key.

User ids are uuid because the web configuration sets generateId to "uuid".
PostgreSQL then fills id with gen_random_uuid(). Column names are the library's
camelCase field names, which is what its Kysely adapter writes.
"""

from alembic import op

revision = "0002_auth"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


UPGRADE = """
create schema if not exists auth;

create table auth."user" (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text not null unique,
  "emailVerified" boolean not null default false,
  image text,
  "createdAt" timestamptz not null default now(),
  "updatedAt" timestamptz not null default now()
);

create table auth.session (
  id uuid primary key default gen_random_uuid(),
  "expiresAt" timestamptz not null,
  token text not null unique,
  "createdAt" timestamptz not null default now(),
  "updatedAt" timestamptz not null default now(),
  "ipAddress" text,
  "userAgent" text,
  "userId" uuid not null references auth."user" (id) on delete cascade
);

create index session_user_id on auth.session ("userId");

create table auth.account (
  id uuid primary key default gen_random_uuid(),
  "accountId" text not null,
  "providerId" text not null,
  "userId" uuid not null references auth."user" (id) on delete cascade,
  "accessToken" text,
  "refreshToken" text,
  "idToken" text,
  "accessTokenExpiresAt" timestamptz,
  "refreshTokenExpiresAt" timestamptz,
  scope text,
  password text,
  "createdAt" timestamptz not null default now(),
  "updatedAt" timestamptz not null default now()
);

create index account_user_id on auth.account ("userId");

create table auth.verification (
  id uuid primary key default gen_random_uuid(),
  identifier text not null,
  value text not null,
  "expiresAt" timestamptz not null,
  "createdAt" timestamptz not null default now(),
  "updatedAt" timestamptz not null default now()
);

create index verification_identifier on auth.verification (identifier);

alter table identity.memberships
  add constraint memberships_user_fk
  foreign key (user_id) references auth."user" (id);
"""

DOWNGRADE = """
alter table identity.memberships drop constraint if exists memberships_user_fk;
drop table if exists auth.verification;
drop table if exists auth.account;
drop table if exists auth.session;
drop table if exists auth."user";
drop schema if exists auth;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
