import { Link } from "react-router-dom";
import { resolveRecipeImageSrc, type MealType, type RecipeRead } from "../../api/recipes";

type RecipeGridCardProps = {
  recipe: RecipeRead;
  mealTypeLabels: Record<MealType, string>;
  favoriteUpdating?: boolean;
  onToggleFavorite?: (recipe: RecipeRead) => void;
};

function formatMetric(value: string | number): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "0";
  if (Number.isInteger(numeric)) return String(numeric);
  return numeric.toFixed(2).replace(/\.?0+$/, "");
}

export function RecipeGridCard({
  recipe,
  mealTypeLabels,
  favoriteUpdating = false,
  onToggleFavorite,
}: RecipeGridCardProps) {
  const imageSrc = resolveRecipeImageSrc(recipe.image_url);

  return (
    <article className="recipe-grid-card">
      <div className="recipe-grid-media-wrap">
        <Link to={`/recipes/${recipe.id}`} className="recipe-grid-media-link" aria-label={`Открыть рецепт: ${recipe.name}`}>
          {imageSrc ? (
            <>
              <img
                src={imageSrc}
                alt={`Фото блюда: ${recipe.name}`}
                className="recipe-grid-image"
                onError={(event) => {
                  event.currentTarget.style.display = "none";
                  const fallback = event.currentTarget.nextElementSibling as HTMLElement | null;
                  if (fallback) fallback.style.display = "grid";
                }}
              />
              <div className="recipe-grid-image-fallback" style={{ display: "none" }} aria-hidden="true">
                {recipe.name.slice(0, 1).toUpperCase()}
              </div>
            </>
          ) : (
            <div className="recipe-grid-image-fallback" aria-hidden="true">
              {recipe.name.slice(0, 1).toUpperCase()}
            </div>
          )}
        </Link>

        {onToggleFavorite && (
          <button
            type="button"
            className={`recipe-grid-favorite-btn ${recipe.is_favorite ? "is-active" : ""}`}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onToggleFavorite(recipe);
            }}
            disabled={favoriteUpdating}
            aria-label={recipe.is_favorite ? "Убрать из избранного" : "Добавить в избранное"}
          >
            <span aria-hidden="true">{recipe.is_favorite ? "♥" : "♡"}</span>
          </button>
        )}
      </div>

      <Link to={`/recipes/${recipe.id}`} className="recipe-grid-body-link">
        <div className="recipe-grid-body">
          <h3 className="recipe-grid-title">{recipe.name}</h3>

          <div className="recipe-grid-tags">
            {recipe.meal_types.map((mealType) => (
              <span key={`${recipe.id}-${mealType}`} className="recipe-grid-tag">
                {mealTypeLabels[mealType]}
              </span>
            ))}
            {typeof recipe.cook_time_minutes === "number" && (
              <span className="recipe-grid-time">{recipe.cook_time_minutes} мин</span>
            )}
          </div>

          <div className="recipe-grid-metrics">
            <p className="recipe-grid-kcal">{formatMetric(recipe.per_serving_kcal)} ккал</p>
            <p className="recipe-grid-macros">
              Б {formatMetric(recipe.per_serving_protein)} · Ж {formatMetric(recipe.per_serving_fat)} · У {formatMetric(recipe.per_serving_carbs)}
            </p>
            <p className="recipe-grid-fiber">Клетчатка {formatMetric(recipe.per_serving_fiber)} г</p>
          </div>

          <p className="recipe-grid-servings">{recipe.servings_count} порции</p>
        </div>
      </Link>
    </article>
  );
}
