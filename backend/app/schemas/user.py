from pydantic import BaseModel, ConfigDict, EmailStr, TypeAdapter, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError
from app.models.enums import UserRole
import re


USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,29}$")  # 3..30
EMAIL_ADAPTER = TypeAdapter(EmailStr)


def _normalize_email(v: str) -> str:
    if not isinstance(v, str):
        raise PydanticCustomError("email_format", "Некорректный формат email.")
    email = v.strip().lower()
    try:
        EMAIL_ADAPTER.validate_python(email)
    except ValidationError:
        raise PydanticCustomError("email_format", "Некорректный формат email.") from None
    return email


def _normalize_username(v: str) -> str:
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


def _validate_password(v: str) -> str:
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


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    display_name: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _normalize_email(v)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return _normalize_username(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)


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
    model_config = ConfigDict(extra="forbid")

    username: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _normalize_username(v)

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "UserUpdateMe":
        if len(self.model_fields_set) == 0:
            raise PydanticCustomError("empty_payload", "Нужно передать хотя бы одно поле для обновления.")
        return self


class UserUpdatePassword(BaseModel):
    current_password: str
    new_password: str

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, value: str) -> str:
        if not value:
            raise PydanticCustomError("password_current_required", "Введите текущий пароль.")
        return value

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password(value)

    @model_validator(mode="after")
    def validate_password_changed(self) -> "UserUpdatePassword":
        if self.current_password == self.new_password:
            raise PydanticCustomError("password_same_as_old", "Новый пароль должен отличаться от текущего.")
        return self


class FavoriteAuthorStateRead(BaseModel):
    author_id: int
    is_favorite: bool


class FavoriteAuthorRead(BaseModel):
    id: int
    username: str
    public_recipes_count: int
    is_favorite: bool = True
