"""Store the PayPal approval URL so the buyer can approve the order."""

from alembic import op

revision = "0012_approval_url"
down_revision = "0011_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table commerce.transactions add column if not exists provider_approval_url text")


def downgrade() -> None:
    op.execute("alter table commerce.transactions drop column if exists provider_approval_url")
