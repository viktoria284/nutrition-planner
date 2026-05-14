import { type MealType, type RecipeCreate } from "../api/recipes";

export type RecipeFormState = {
  name: string;
  description: string;
  instructions: string;
  image_url: string;
  servings_count: string;
  cook_time_minutes: string;
  meal_types: MealType[];
};

export type RecipeFormErrors = {
  name?: string;
  servings_count?: string;
  cook_time_minutes?: string;
  image_url?: string;
  meal_types?: string;
  form: string[];
};

export const EMPTY_RECIPE_FORM: RecipeFormState = {
  name: "",
  description: "",
  instructions: "",
  image_url: "",
  servings_count: "1",
  cook_time_minutes: "",
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
  instructions?: string | null;
  image_url?: string | null;
  servings_count: number;
  cook_time_minutes?: number | null;
  meal_types: MealType[];
}): RecipeFormState {
  return {
    name: input.name,
    description: input.description ?? "",
    instructions: input.instructions ?? "",
    image_url: input.image_url ?? "",
    servings_count: String(input.servings_count),
    cook_time_minutes: input.cook_time_minutes === null || input.cook_time_minutes === undefined ? "" : String(input.cook_time_minutes),
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

  const cookTimeRaw = form.cook_time_minutes.trim();
  let cookTime: number | null = null;
  if (cookTimeRaw) {
    const parsedCookTime = Number(cookTimeRaw);
    if (!Number.isInteger(parsedCookTime) || parsedCookTime < 1 || parsedCookTime > 1440) {
      errors.cook_time_minutes = "Введите целое число от 1 до 1440.";
      errors.form.push("Время приготовления должно быть целым числом от 1 до 1440.");
    } else {
      cookTime = parsedCookTime;
    }
  }

  const imageUrl = form.image_url.trim();
  if (imageUrl) {
    const isHttpUrl = /^https?:\/\/\S+$/i.test(imageUrl);
    if (!isHttpUrl) {
      errors.image_url = "Укажите корректную ссылку http:// или https://.";
      errors.form.push("Ссылка на изображение должна начинаться с http:// или https://.");
    }
  }

  if (errors.form.length > 0) {
    return { errors, payload: null };
  }

  const description = form.description.trim();
  const instructions = form.instructions.trim();

  return {
    errors: { form: [] },
    payload: {
      name,
      description: description || null,
      instructions: instructions || null,
      image_url: imageUrl || null,
      servings_count: servings,
      meal_types: form.meal_types,
      ...(cookTime !== null ? { cook_time_minutes: cookTime } : {}),
    },
  };
}
