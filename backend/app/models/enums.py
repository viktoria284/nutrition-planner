from enum import Enum


class UserRole(str, Enum):
    user = "user"
    admin = "admin"
    superadmin = "superadmin"


class FoodSource(str, Enum):
    private = "private"
    verified = "verified"
    community = "community"


class FoodStatus(str, Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
