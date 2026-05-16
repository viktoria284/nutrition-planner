from pydantic import BaseModel, EmailStr, TypeAdapter, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError
from app.models.enums import UserRole
import re


USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,29}$")  # 3..30
EMAIL_ADAPTER = TypeAdapter(EmailStr)


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    display_name: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not isinstance(v, str):
            raise PydanticCustomError("email_format", "Некорректный формат email.")
        email = v.strip().lower()
        try:
            EMAIL_ADAPTER.validate_python(email)
        except ValidationError:
            raise PydanticCustomError("email_format", "Некорректный формат email.") from None
        return email

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise PydanticCustomError(
                "username_format",
                "Username должен начинаться с буквы и содержать только латинские буквы, цифры или _. Длина — 3–30 символов.",
            )
        reserved = {"admin", "root", "auth", "me", "api", "support"}
        if v in reserved:
            raise PydanticCustomError("username_reserved", "Username зарезервирован.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not (8 <= len(v) <= 128):
            raise PydanticCustomError("password_length", "Пароль должен быть длиной от 8 символов.")
        if len(v.encode("utf-8")) > 256:
            raise PydanticCustomError("password_too_long", "Пароль слишком длинный.")
        if any(ch.isspace() for ch in v):
            raise PydanticCustomError("password_whitespace", "Пароль не должен содержать пробелы.")

        has_letter = any(ch.isalpha() for ch in v)
        has_digit = any(ch.isdigit() for ch in v)
        has_special = any(not ch.isalnum() for ch in v)

        if not has_letter:
            raise PydanticCustomError("password_letter", "Пароль должен содержать хотя бы одну букву.")
        if not has_digit:
            raise PydanticCustomError("password_digit", "Пароль должен содержать хотя бы одну цифру.")
        if not has_special:
            raise PydanticCustomError("password_special", "Пароль должен содержать хотя бы один спецсимвол.")
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


class UserUpdateMe(BaseModel):
    email: EmailStr | None = None
    username: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise PydanticCustomError("email_format", "Некорректный формат email.")
        email = v.strip().lower()
        try:
            EMAIL_ADAPTER.validate_python(email)
        except ValidationError:
            raise PydanticCustomError("email_format", "Некорректный формат email.") from None
        return email

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower()
        if not USERNAME_RE.match(normalized):
            raise PydanticCustomError(
                "username_format",
                "Username должен начинаться с буквы и содержать только латинские буквы, цифры или _. Длина — 3–30 символов.",
            )
        reserved = {"admin", "root", "auth", "me", "api", "support"}
        if normalized in reserved:
            raise PydanticCustomError("username_reserved", "Username зарезервирован.")
        return normalized

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "UserUpdateMe":
        if len(self.model_fields_set) == 0:
            raise PydanticCustomError("empty_payload", "Нужно передать хотя бы одно поле для обновления.")
        return self


class FavoriteAuthorStateRead(BaseModel):
    author_id: int
    is_favorite: bool


class FavoriteAuthorRead(BaseModel):
    id: int
    username: str
    public_recipes_count: int
    is_favorite: bool = True
