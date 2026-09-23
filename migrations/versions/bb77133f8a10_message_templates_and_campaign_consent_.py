"""message templates, campaign consent option, per-message reserved credits

Revision ID: bb77133f8a10
Revises: 1681930e4c90
Create Date: 2026-09-23 14:00:42.897628

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bb77133f8a10'
down_revision = '1681930e4c90'
branch_labels = None
depends_on = None


def upgrade():
    
    op.create_table('message_templates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('business_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('body', sa.String(length=640), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name=op.f('fk_message_templates_business_id_businesses')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_message_templates')),
    sa.UniqueConstraint('business_id', 'name', name='uq_template_name_per_business')
    )
    with op.batch_alter_table('message_templates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_message_templates_business_id'), ['business_id'], unique=False)

    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('consent_only', sa.Boolean(), server_default=sa.false(), nullable=False))

    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('credits_reserved', sa.Integer(), server_default='0', nullable=False))

    


def downgrade():
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_column('credits_reserved')

    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('consent_only')

    with op.batch_alter_table('message_templates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_message_templates_business_id'))

    op.drop_table('message_templates')
    
