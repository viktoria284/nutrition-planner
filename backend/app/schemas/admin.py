from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import FoodSource, FoodStatus, UserRole

AdminTargetType = Literal["food", "recipe"]
AdminModerationAction = Literal["approve", "hide", "reject", "restore"]
AdminReportResolution = Literal["no_action", "content_hidden", "content_restored", "content_rejected"]
AdminContentOrigin = Literal["all", "system", "user"]


class AdminOwnerRead(BaseModel):
    id: int
    username: str
    display_name: str | None = None


class AdminSummaryRead(BaseModel):
    total_users: int
    total_foods: int
    total_recipes: int
    public_foods: int
    public_recipes: int
    pending_or_under_review_foods: int
    pending_or_under_review_recipes: int
    open_food_reports: int
    open_recipe_reports: int


class AdminFoodListItemRead(BaseModel):
    id: int
    name: str
    brand: str | None = None
    category: str
    kcal: float
    protein: float
    fat: float
    carbs: float
    fiber: float
    source: FoodSource
    status: FoodStatus
    is_listed: bool
    reports_count: int
    owner: AdminOwnerRead | None = None
    created_at: datetime
    updated_at: datetime


class AdminRecipeListItemRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    instructions: str | None = None
    servings_count: int
    cook_time_minutes: int | None = None
    source: FoodSource
    status: FoodStatus
    is_listed: bool
    meal_types: list[str]
    reports_count: int
    owner: AdminOwnerRead | None = None
    created_at: datetime
    updated_at: datetime


class AdminReportRead(BaseModel):
    id: int
    target_type: AdminTargetType
    target_id: int
    target_name: str
    reporter: AdminOwnerRead | None = None
    reason: str | None = None
    comment: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    resolution: str | None = None
    resolved_by_admin: AdminOwnerRead | None = None
    admin_comment: str | None = None


class AdminModerateRequest(BaseModel):
    action: AdminModerationAction
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AdminResolveReportRequest(BaseModel):
    resolution: AdminReportResolution
    comment: str | None = None

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AdminUserListItemRead(BaseModel):
    id: int
    email: str
    username: str
    display_name: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
    profiles_count: int = 0
    recipes_count: int = 0
    plans_count: int = 0


class AdminRoleUpdateRequest(BaseModel):
    role: UserRole

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: UserRole) -> UserRole:
        if value not in {UserRole.user, UserRole.admin, UserRole.superadmin}:
            raise ValueError("Invalid role")
        return value


class AdminFoodsQuery(BaseModel):
    q: str | None = None
    source: FoodSource | None = None
    origin: AdminContentOrigin = "all"
    status: FoodStatus | None = None
    is_listed: bool | None = None
    reported_only: bool = False
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class AdminRecipesQuery(BaseModel):
    q: str | None = None
    origin: AdminContentOrigin = "all"
    status: FoodStatus | None = None
    is_listed: bool | None = None
    reported_only: bool = False
    meal_type: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class AdminReportsQuery(BaseModel):
    target_type: Literal["food", "recipe", "all"] = "all"
    only_open: bool = True
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class AdminUsersQuery(BaseModel):
    q: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
