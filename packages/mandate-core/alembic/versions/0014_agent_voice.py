"""Publish a voice selection with each immutable agent version."""

from alembic import op

revision = "0014_agent_voice"
down_revision = "0013_merchant_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table agents.agent_versions add column if not exists voice_id text")
    op.execute("""create or replace function agents.prevent_version_edit() returns trigger
        language plpgsql as $$ begin
        if new.provider is distinct from old.provider
           or new.model is distinct from old.model
           or new.temperature is distinct from old.temperature
           or new.fallbacks is distinct from old.fallbacks
           or new.system_prompt is distinct from old.system_prompt
           or new.skill_names is distinct from old.skill_names
           or new.voice_id is distinct from old.voice_id then
          raise exception 'agent version is immutable' using errcode = '23514';
        end if;
        return new;
        end $$""")


def downgrade() -> None:
    op.execute("alter table agents.agent_versions drop column if exists voice_id")
