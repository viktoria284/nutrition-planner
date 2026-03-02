import { type MealType, type RecipeCreate } from "../api/recipes";

export type RecipeFormState = {
  name: string;
  description: string;
  servings_count: string;
  meal_types: MealType[];
};

export type RecipeFormErrors = {
  name?: string;
  servings_count?: string;
  meal_types?: string;
  form: string[];
};

export const EMPTY_RECIPE_FORM: RecipeFormState = {
  name: "",
  description: "",
  servings_count: "1",
  meal_types: [],
};

export const RECIPE_MEAL_TYPE_OPTIONS: Array<{ value: MealType; label: string }> = [
  { value: "breakfast", label: "Завтрак" },
  { value: "lunch", label: "Обед" },
  { value: "dinner", label: "Ужин" },
  { value: "snack", label: "Перекус" },
];

export function toRecipeFormState(input: {
  name: string;
  description?: string | null;
  servings_count: number;
  meal_types: MealType[];
}): RecipeFormState {
  return {
    name: input.name,
    description: input.description ?? "",
    servings_count: String(input.servings_count),
    meal_types: input.meal_types,
  };
}

export function validateRecipeForm(form: RecipeFormState): { errors: RecipeFormErrors; payload: RecipeCreate | null } {
  const errors: RecipeFormErrors = { form: [] };

  const name = form.name.trim();
  if (!name) {
    errors.name = "Введите название рецепта.";
    errors.form.push("Название обязательно.");
  }

  const servingsRaw = form.servings_count.trim();
  const servings = Number(servingsRaw);
  if (!servingsRaw || !Number.isInteger(servings) || servings < 1) {
    errors.servings_count = "Введите целое число не меньше 1.";
    errors.form.push("Количество порций должно быть целым числом от 1.");
  }

  if (form.meal_types.length === 0) {
    errors.meal_types = "Выберите хотя бы один тип приёма пищи.";
    errors.form.push("Выберите хотя бы один тип приёма пищи.");
  }

  if (errors.form.length > 0) {
    return { errors, payload: null };
  }

  const description = form.description.trim();

  return {
    errors: { form: [] },
    payload: {
      name,
      servings_count: servings,
      meal_types: form.meal_types,
      ...(description ? { description } : {}),
    },
  };
}
