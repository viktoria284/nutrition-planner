from sqlalchemy import ForeignKey, Integer, String
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

    user: Mapped["User"] = relationship("User", back_populates="profiles")
