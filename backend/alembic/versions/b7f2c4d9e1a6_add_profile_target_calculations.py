"""add profile target calculations

Revision ID: b7f2c4d9e1a6
Revises: a6f9b2c3d4e5
Create Date: 2026-05-27 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7f2c4d9e1a6"
down_revision = "a6f9b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profile_target_calculations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sex", sa.String(length=16), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("height_cm", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("weight_kg", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("activity_level", sa.String(length=24), nullable=False),
        sa.Column("goal", sa.String(length=24), nullable=False),
        sa.Column("formula", sa.String(length=32), nullable=False),
        sa.Column("macro_preset", sa.String(length=24), nullable=False),
        sa.Column(
            "is_pregnant_or_lactating",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "has_medical_condition_requiring_special_diet",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("bmr", sa.Integer(), nullable=False),
        sa.Column("tdee", sa.Integer(), nullable=False),
        sa.Column("target_kcal", sa.Integer(), nullable=False),
        sa.Column("target_protein", sa.Numeric(precision=8, scale=1), nullable=False),
        sa.Column("target_fat", sa.Numeric(precision=8, scale=1), nullable=False),
        sa.Column("target_carbs", sa.Numeric(precision=8, scale=1), nullable=False),
        sa.Column("target_fiber", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("warning_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_profile_target_calculations_user_id"),
    )
    op.create_index(
        op.f("ix_profile_target_calculations_user_id"),
        "profile_target_calculations",
        ["user_id"],
        unique=True,
    )

    op.create_check_constraint(
        "ck_profile_target_calculations_sex_allowed",
        "profile_target_calculations",
        "sex IN ('male', 'female')",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_activity_level_allowed",
        "profile_target_calculations",
        "activity_level IN ('sedentary', 'light', 'moderate', 'active', 'very_active')",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_goal_allowed",
        "profile_target_calculations",
        "goal IN ('maintain', 'lose', 'gain')",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_formula_allowed",
        "profile_target_calculations",
        "formula IN ('mifflin_st_jeor', 'revised_harris_benedict', 'who_fao_unu')",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_macro_preset_allowed",
        "profile_target_calculations",
        "macro_preset IN ('balanced', 'higher_protein', 'higher_carb')",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_age_range",
        "profile_target_calculations",
        "age BETWEEN 18 AND 100",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_height_range",
        "profile_target_calculations",
        "height_cm BETWEEN 100 AND 250",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_weight_range",
        "profile_target_calculations",
        "weight_kg BETWEEN 30 AND 300",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_bmr_positive",
        "profile_target_calculations",
        "bmr > 0",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_tdee_positive",
        "profile_target_calculations",
        "tdee > 0",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_target_kcal_positive",
        "profile_target_calculations",
        "target_kcal > 0",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_target_protein_non_negative",
        "profile_target_calculations",
        "target_protein >= 0",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_target_fat_non_negative",
        "profile_target_calculations",
        "target_fat >= 0",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_target_carbs_non_negative",
        "profile_target_calculations",
        "target_carbs >= 0",
    )
    op.create_check_constraint(
        "ck_profile_target_calculations_target_fiber_non_negative",
        "profile_target_calculations",
        "target_fiber >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_profile_target_calculations_target_fiber_non_negative",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_target_carbs_non_negative",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_target_fat_non_negative",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_target_protein_non_negative",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_target_kcal_positive",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_tdee_positive",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_bmr_positive",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_weight_range",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_height_range",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_age_range",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_macro_preset_allowed",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_formula_allowed",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_goal_allowed",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_activity_level_allowed",
        "profile_target_calculations",
        type_="check",
    )
    op.drop_constraint(
        "ck_profile_target_calculations_sex_allowed",
        "profile_target_calculations",
        type_="check",
    )

    op.drop_index(op.f("ix_profile_target_calculations_user_id"), table_name="profile_target_calculations")
    op.drop_table("profile_target_calculations")
