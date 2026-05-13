from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    target_kcal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_protein: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_fat: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_carbs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_categories: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    max_cook_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="profiles")
    excluded_food_links: Mapped[list["ProfileExcludedFood"]] = relationship(
        "ProfileExcludedFood",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    preferred_food_links: Mapped[list["ProfilePreferredFood"]] = relationship(
        "ProfilePreferredFood",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "max_cook_time_minutes IS NULL OR (max_cook_time_minutes BETWEEN 1 AND 1440)",
            name="ck_profiles_max_cook_time_minutes_range",
        ),
    )

    @property
    def excluded_food_ids(self) -> list[int]:
        return sorted(link.food_id for link in self.excluded_food_links)

    @property
    def preferred_food_ids(self) -> list[int]:
        return sorted(link.food_id for link in self.preferred_food_links)


class ProfileExcludedFood(Base):
    __tablename__ = "profile_excluded_foods"

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    food_id: Mapped[int] = mapped_column(
        ForeignKey("food_items.id", ondelete="CASCADE"),
        primary_key=True,
    )

    profile: Mapped[Profile] = relationship("Profile", back_populates="excluded_food_links")


class ProfilePreferredFood(Base):
    __tablename__ = "profile_preferred_foods"

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    food_id: Mapped[int] = mapped_column(
        ForeignKey("food_items.id", ondelete="CASCADE"),
        primary_key=True,
    )

    profile: Mapped[Profile] = relationship("Profile", back_populates="preferred_food_links")
