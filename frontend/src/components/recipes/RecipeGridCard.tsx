import { Link } from "react-router-dom";
import { resolveRecipeImageSrc, type MealType, type RecipeRead } from "../../api/recipes";
import { formatRoundedNumber } from "../../utils/numberFormat";

type RecipeGridCardProps = {
  recipe: RecipeRead;
  mealTypeLabels: Record<MealType, string>;
  favoriteUpdating?: boolean;
  onToggleFavorite?: (recipe: RecipeRead) => void;
  onAuthorClick?: (recipe: RecipeRead) => void;
};

export function RecipeGridCard({
  recipe,
  mealTypeLabels,
  favoriteUpdating = false,
  onToggleFavorite,
  onAuthorClick,
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
            <p className="recipe-grid-kcal">{formatRoundedNumber(recipe.per_serving_kcal)} ккал</p>
            <p className="recipe-grid-macros">
              Б {formatRoundedNumber(recipe.per_serving_protein)} г · Ж {formatRoundedNumber(recipe.per_serving_fat)} г · У {formatRoundedNumber(recipe.per_serving_carbs)} г
            </p>
            <p className="recipe-grid-fiber">Клетчатка {formatRoundedNumber(recipe.per_serving_fiber)} г</p>
          </div>

          <div className="recipe-grid-meta-bottom">
            <p className="recipe-grid-servings">{recipe.servings_count} порции</p>
            {(onAuthorClick || recipe.source === "community") && recipe.author_username ? (
              onAuthorClick ? (
                <button
                  type="button"
                  className="recipe-grid-author-link"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    onAuthorClick(recipe);
                  }}
                >
                  Автор: @{recipe.author_username}
                </button>
              ) : (
                <p className="recipe-grid-author">Автор: @{recipe.author_username}</p>
              )
            ) : (
              <p className="recipe-grid-author">{recipe.source === "community" ? "Автор: —" : "Ваш рецепт"}</p>
            )}
          </div>
        </div>
      </Link>
    </article>
  );
}
