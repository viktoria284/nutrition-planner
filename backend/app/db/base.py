from app.db.base_class import Base
from app.models.author_favorite import AuthorFavorite  # noqa: F401
from app.models.foods import FoodItem, FoodReport, FoodServing  # noqa: F401
from app.models.pantry import UserPantryItem  # noqa: F401
from app.models.plan import Plan  # noqa: F401
from app.models.plan_slot import PlanSlot, PlanSlotIngredientOverride  # noqa: F401
from app.models.profile import Profile, ProfileExcludedFood, ProfilePreferredFood  # noqa: F401
from app.models.profile_target_calculation import ProfileTargetCalculation  # noqa: F401
from app.models.recipe import Recipe, RecipeFavorite, RecipeIngredient, RecipeNote, RecipeReport, RecipeStep  # noqa: F401
from app.models.shopping import ShoppingList, ShoppingListItem, ShoppingListSource  # noqa: F401
from app.models.user import User  # noqa: F401
