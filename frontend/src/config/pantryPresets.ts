export type PantryPresetItem = {
  key: string;
  label: string;
  aliases: string[];
};

export type PantryPresetCategory = {
  key: string;
  title: string;
  defaultOpen?: boolean;
  items: PantryPresetItem[];
};

export const PANTRY_PRESET_CATEGORIES: PantryPresetCategory[] = [
  {
    key: "spices_basics",
    title: "Специи и базовые добавки",
    defaultOpen: true,
    items: [
      { key: "salt", label: "Соль", aliases: ["Соль"] },
      { key: "black_pepper", label: "Перец чёрный", aliases: ["Перец черный молотый", "Перец черный"] },
      { key: "paprika", label: "Паприка", aliases: ["Паприка"] },
      { key: "cinnamon", label: "Корица", aliases: ["Корица"] },
      { key: "sugar", label: "Сахар", aliases: ["Сахар"] },
      { key: "tomato_paste", label: "Томатная паста", aliases: ["Томатная паста"] },
      { key: "soy_sauce", label: "Соевый соус", aliases: ["Соевый соус"] },
    ],
  },
  {
    key: "oils_sauces",
    title: "Масла и соусы",
    defaultOpen: true,
    items: [
      {
        key: "vegetable_oil",
        label: "Масло растительное",
        aliases: ["Масло растительное", "Подсолнечное масло"],
      },
      { key: "olive_oil", label: "Масло оливковое", aliases: ["Масло оливковое", "Оливковое масло"] },
      { key: "butter", label: "Масло сливочное", aliases: ["Масло сливочное"] },
      { key: "vinegar", label: "Уксус", aliases: ["Уксус"] },
      { key: "mustard", label: "Горчица", aliases: ["Горчица"] },
    ],
  },
  {
    key: "vegetable_base",
    title: "Овощная база",
    defaultOpen: true,
    items: [
      { key: "onion", label: "Лук репчатый", aliases: ["Лук репчатый"] },
      { key: "garlic", label: "Чеснок", aliases: ["Чеснок"] },
      { key: "carrot", label: "Морковь", aliases: ["Морковь"] },
      { key: "potato", label: "Картофель", aliases: ["Картофель", "Картофель отварной"] },
      { key: "cucumber", label: "Огурец", aliases: ["Огурец"] },
      { key: "tomato", label: "Томат", aliases: ["Томат", "Помидор"] },
    ],
  },
  {
    key: "grains_bread",
    title: "Крупы, макароны и хлеб",
    items: [
      { key: "rice", label: "Рис", aliases: ["Рис", "Рис отварной"] },
      { key: "buckwheat", label: "Гречка", aliases: ["Гречка", "Гречка отварная"] },
      { key: "oats", label: "Овсяные хлопья", aliases: ["Овсяные хлопья"] },
      { key: "pasta", label: "Макароны", aliases: ["Макароны", "Макароны отварные"] },
      { key: "bulgur", label: "Булгур", aliases: ["Булгур", "Булгур отварной"] },
      { key: "couscous", label: "Кускус", aliases: ["Кускус", "Кускус отварной"] },
      { key: "wholegrain_bread", label: "Хлеб цельнозерновой", aliases: ["Хлеб цельнозерновой"] },
    ],
  },
  {
    key: "dairy_eggs",
    title: "Молочное и яйца",
    items: [
      { key: "egg", label: "Яйцо куриное", aliases: ["Яйцо куриное"] },
      { key: "milk", label: "Молоко", aliases: ["Молоко", "Молоко 2.5%"] },
      { key: "kefir", label: "Кефир", aliases: ["Кефир", "Кефир 1%"] },
      { key: "cottage_cheese", label: "Творог", aliases: ["Творог", "Творог 5%"] },
      { key: "greek_yogurt", label: "Йогурт греческий", aliases: ["Йогурт греческий"] },
    ],
  },
  {
    key: "legumes_canned",
    title: "Бобовые и консервы",
    items: [
      { key: "chickpeas", label: "Нут", aliases: ["Нут", "Нут вареный"] },
      { key: "beans", label: "Фасоль", aliases: ["Фасоль", "Фасоль красная вареная"] },
      { key: "lentils", label: "Чечевица", aliases: ["Чечевица", "Чечевица вареная"] },
      { key: "tuna", label: "Тунец консервированный", aliases: ["Тунец консервированный"] },
      { key: "canned_corn", label: "Кукуруза консервированная", aliases: ["Кукуруза консервированная"] },
    ],
  },
  {
    key: "nuts_seeds_dry",
    title: "Орехи, семена, сухие продукты",
    items: [
      { key: "nuts", label: "Орехи", aliases: ["Орехи", "Орехи грецкие"] },
      { key: "flax", label: "Семена льна", aliases: ["Семена льна"] },
      { key: "peanut_butter", label: "Арахисовая паста", aliases: ["Арахисовая паста"] },
      { key: "honey", label: "Мёд", aliases: ["Мёд"] },
    ],
  },
];
