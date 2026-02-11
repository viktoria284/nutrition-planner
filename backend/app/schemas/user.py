from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str

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
    is_active: bool

    class Config:
        from_attributes = True
