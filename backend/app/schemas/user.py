from pydantic import BaseModel, EmailStr, field_validator
from app.models.enums import UserRole
import re


USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,29}$")  # 3..30


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    display_name: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise ValueError("username: 3–30, латиница/цифры/_, начинается с буквы")
        reserved = {"admin", "root", "auth", "me", "api", "support"}
        if v in reserved:
            raise ValueError("username зарезервирован")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not (8 <= len(v) <= 128):
            raise ValueError("Пароль должен быть длиной 8–128 символов")
        if len(v.encode("utf-8")) > 256:
            raise ValueError("Пароль слишком длинный")
        if any(ch.isspace() for ch in v):
            raise ValueError("Пароль не должен содержать пробелы")

        has_letter = any(ch.isalpha() for ch in v)
        has_digit = any(ch.isdigit() for ch in v)
        has_special = any(not ch.isalnum() for ch in v)

        if not has_letter:
            raise ValueError("Пароль должен содержать хотя бы одну букву")
        if not has_digit:
            raise ValueError("Пароль должен содержать хотя бы одну цифру")
        if not has_special:
            raise ValueError("Пароль должен содержать хотя бы один спецсимвол")
        return v


class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: str
    display_name: str | None
    is_active: bool
    role: UserRole

    class Config:
        from_attributes = True
