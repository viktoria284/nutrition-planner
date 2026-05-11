export const FOOD_CATEGORIES = [
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
] as const;

export type FoodCategory = (typeof FOOD_CATEGORIES)[number];

export const FOOD_CATEGORY_LABELS: Record<FoodCategory, string> = {
  vegetables: "Овощи",
  fruits: "Фрукты и ягоды",
  dairy: "Молочные продукты",
  eggs: "Яйца",
  meat_fish: "Мясо и рыба",
  grains_bakery: "Крупы и выпечка",
  pantry_spices: "Бакалея и специи",
  nuts_oils: "Орехи и масла",
  drinks: "Напитки",
  sweets: "Сладости",
  frozen: "Заморозка",
  other: "Другое",
};

export function isFoodCategory(value: string): value is FoodCategory {
  return FOOD_CATEGORIES.includes(value as FoodCategory);
}
