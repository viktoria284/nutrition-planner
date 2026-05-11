from __future__ import annotations

FOOD_CATEGORIES: tuple[str, ...] = (
    "vegetables",
    "fruits",
    "dairy",
    "eggs",
    "meat_fish",
    "grains_bakery",
    "pantry_spices",
    "nuts_oils",
    "drinks",
    "sweets",
    "frozen",
    "other",
)

DEFAULT_FOOD_CATEGORY = "other"
FOOD_CATEGORIES_SET = set(FOOD_CATEGORIES)

SHOPPING_LIST_STATUSES: tuple[str, ...] = ("active", "archived")
DEFAULT_SHOPPING_LIST_STATUS = "active"

SHOPPING_LIST_SOURCE_TYPES: tuple[str, ...] = ("plan",)
DEFAULT_SHOPPING_LIST_SOURCE_TYPE = "plan"

SHOPPING_ITEM_TYPES: tuple[str, ...] = ("computed", "manual")
