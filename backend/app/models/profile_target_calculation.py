from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ProfileTargetCalculation(Base):
    __tablename__ = "profile_target_calculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    sex: Mapped[str] = mapped_column(String(16), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    height_cm: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    activity_level: Mapped[str] = mapped_column(String(24), nullable=False)
    goal: Mapped[str] = mapped_column(String(24), nullable=False)
    formula: Mapped[str] = mapped_column(String(32), nullable=False)
    macro_preset: Mapped[str] = mapped_column(String(24), nullable=False)

    special_condition: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="none",
        default="none",
    )
    lactation_period: Mapped[str | None] = mapped_column(String(24), nullable=True)

    bmr: Mapped[int] = mapped_column(Integer, nullable=False)
    tdee: Mapped[int] = mapped_column(Integer, nullable=False)
    target_kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    target_protein: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False)
    target_fat: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False)
    target_carbs: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False)
    target_fiber: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)

    warning_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="latest_profile_target_calculation")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_profile_target_calculations_user_id"),
        CheckConstraint("sex IN ('male', 'female')", name="ck_profile_target_calculations_sex_allowed"),
        CheckConstraint(
            "activity_level IN ('sedentary', 'light', 'moderate', 'active', 'very_active')",
            name="ck_profile_target_calculations_activity_level_allowed",
        ),
        CheckConstraint("goal IN ('maintain', 'lose', 'gain')", name="ck_profile_target_calculations_goal_allowed"),
        CheckConstraint(
            "formula IN ('mifflin_st_jeor', 'revised_harris_benedict', 'who_fao_unu')",
            name="ck_profile_target_calculations_formula_allowed",
        ),
        CheckConstraint(
            "macro_preset IN ('balanced', 'higher_protein', 'higher_carb')",
            name="ck_profile_target_calculations_macro_preset_allowed",
        ),
        CheckConstraint(
            "special_condition IN ('none', 'pregnant', 'breastfeeding', 'medical_special_diet')",
            name="ck_profile_target_calculations_special_condition_allowed",
        ),
        CheckConstraint(
            "lactation_period IS NULL OR lactation_period IN ('first_6_months', 'after_6_months', 'unknown')",
            name="ck_profile_target_calculations_lactation_period_allowed",
        ),
        CheckConstraint(
            "(special_condition = 'breastfeeding' AND lactation_period IS NOT NULL) OR "
            "(special_condition != 'breastfeeding' AND lactation_period IS NULL)",
            name="ck_profile_target_calculations_lactation_bf_required",
        ),
        CheckConstraint("age BETWEEN 18 AND 100", name="ck_profile_target_calculations_age_range"),
        CheckConstraint("height_cm BETWEEN 100 AND 250", name="ck_profile_target_calculations_height_range"),
        CheckConstraint("weight_kg BETWEEN 30 AND 300", name="ck_profile_target_calculations_weight_range"),
        CheckConstraint("bmr > 0", name="ck_profile_target_calculations_bmr_positive"),
        CheckConstraint("tdee > 0", name="ck_profile_target_calculations_tdee_positive"),
        CheckConstraint("target_kcal > 0", name="ck_profile_target_calculations_target_kcal_positive"),
        CheckConstraint(
            "target_protein >= 0",
            name="ck_profile_target_calculations_target_protein_non_negative",
        ),
        CheckConstraint("target_fat >= 0", name="ck_profile_target_calculations_target_fat_non_negative"),
        CheckConstraint("target_carbs >= 0", name="ck_profile_target_calculations_target_carbs_non_negative"),
        CheckConstraint("target_fiber >= 0", name="ck_profile_target_calculations_target_fiber_non_negative"),
    )
