"""add special condition fields to profile target calculations

Revision ID: c8f1e2d3a4b5
Revises: b7f2c4d9e1a6
Create Date: 2026-05-27 14:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8f1e2d3a4b5"
down_revision = "b7f2c4d9e1a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profile_target_calculations",
        sa.Column(
            "special_condition",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
    )
    op.add_column(
        "profile_target_calculations",
        sa.Column(
            "lactation_period",
            sa.String(length=24),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE profile_target_calculations
        SET special_condition = CASE
            WHEN has_medical_condition_requiring_special_diet THEN 'medical_special_diet'
            WHEN is_pregnant_or_lactating THEN 'pregnant'
            ELSE 'none'
        END
        """
    )

    op.create_check_constraint(
        "ck_profile_target_calculations_special_condition_allowed",
        "profile_target_calculations",
        "special_condition IN ('none', 'pregnant', 'breastfeeding', 'medical_special_diet')",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_lactation_period_allowed",
        "profile_target_calculations",
        "lactation_period IS NULL OR lactation_period IN ('first_6_months', 'after_6_months', 'unknown')",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_lactation_bf_required",
        "profile_target_calculations",
        "(special_condition = 'breastfeeding' AND lactation_period IS NOT NULL) OR "
        "(special_condition != 'breastfeeding' AND lactation_period IS NULL)",
    )

    op.alter_column(
        "profile_target_calculations",
        "special_condition",
        server_default=sa.text("'none'"),
    )

    op.drop_column("profile_target_calculations", "has_medical_condition_requiring_special_diet")
    op.drop_column("profile_target_calculations", "is_pregnant_or_lactating")


def downgrade() -> None:
    op.add_column(
        "profile_target_calculations",
        sa.Column(
            "is_pregnant_or_lactating",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "profile_target_calculations",
        sa.Column(
            "has_medical_condition_requiring_special_diet",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.execute(
        """
        UPDATE profile_target_calculations
        SET is_pregnant_or_lactating = CASE
                WHEN special_condition IN ('pregnant', 'breastfeeding') THEN true
                ELSE false
            END,
            has_medical_condition_requiring_special_diet = CASE
                WHEN special_condition = 'medical_special_diet' THEN true
                ELSE false
            END
        """
    )

    op.drop_constraint(
        "ck_profile_target_calculations_lactation_bf_required",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_lactation_period_allowed",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_special_condition_allowed",
        "profile_target_calculations",
        type_="check",
    )

    op.drop_column("profile_target_calculations", "lactation_period")
    op.drop_column("profile_target_calculations", "special_condition")
