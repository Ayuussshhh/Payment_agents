"""The application role needs to lock an agent row while publishing a version."""

from alembic import op

revision = "0007_agent_lock"
down_revision = "0006_skills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("grant update on agents.agents to mandate_app")


def downgrade() -> None:
    op.execute("revoke update on agents.agents from mandate_app")
