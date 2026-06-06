import type { CSSProperties } from "react";
import type { MealType } from "../../api/recipes";
import "./RecipePlaceholder.css";

type RecipePlaceholderProps = {
  name: string;
  mealTypes?: MealType[];
  className?: string;
  compact?: boolean;
  style?: CSSProperties;
};

type PlaceholderMeta = { icon: string };

const FALLBACK_PLACEHOLDER_META: PlaceholderMeta = {
  icon: "🍽️",
};

const MEAL_PLACEHOLDER_META: Record<MealType, PlaceholderMeta> = {
  breakfast: { icon: "☀️" },
  lunch: { icon: "🥗" },
  dinner: { icon: "🍲" },
  snack: { icon: "🍓" },
};

function resolvePlaceholderMeta(mealTypes?: MealType[]): { key: MealType | "default"; meta: PlaceholderMeta } {
  const primaryMealType = mealTypes?.[0] as string | undefined;
  if (primaryMealType && Object.prototype.hasOwnProperty.call(MEAL_PLACEHOLDER_META, primaryMealType)) {
    const key = primaryMealType as MealType;
    return { key, meta: MEAL_PLACEHOLDER_META[key] };
  }
  return { key: "default", meta: FALLBACK_PLACEHOLDER_META };
}

export function RecipePlaceholder({ mealTypes, className, compact = false, style }: RecipePlaceholderProps) {
  const { key, meta } = resolvePlaceholderMeta(mealTypes);

  return (
    <div
      className={[
        "recipe-placeholder",
        `recipe-placeholder--${key}`,
        compact ? "recipe-placeholder--compact" : "",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={style}
      aria-hidden="true"
    >
      <span className="recipe-placeholder-pattern" />
      <span className="recipe-placeholder-orb">{meta.icon}</span>
    </div>
  );
}
