import type { DecimalString } from "./plan";
import type { FoodCategory } from "./foodCategory";

export type ShoppingItemType = "computed" | "manual";

export type ShoppingListSource = {
  id: number;
  shopping_list_id: number;
  plan_id: number;
  date_from: string | null;
  date_to: string | null;
  created_at: string;
};

export type ShoppingListItem = {
  id: number;
  shopping_list_id: number;
  food_id: number | null;
  name_snapshot: string;
  category: FoodCategory;
  item_type: ShoppingItemType;
  planned_grams: DecimalString | null;
  adjusted_grams: DecimalString | null;
  effective_grams: DecimalString | null;
  unit: string;
  checked: boolean;
  excluded: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type ShoppingListRead = {
  id: number;
  owner_user_id: number;
  title: string;
  status: string;
  source_type: string;
  source_signature: string | null;
  is_outdated: boolean;
  generated_at: string;
  created_at: string;
  updated_at: string;
  sources: ShoppingListSource[];
  items: ShoppingListItem[];
};

export type ShoppingListSummary = {
  id: number;
  owner_user_id: number;
  title: string;
  status: string;
  source_type: string;
  source_signature: string | null;
  is_outdated: boolean;
  generated_at: string;
  created_at: string;
  updated_at: string;
  source_plan_ids: number[];
  items_total: number;
};

export type ShoppingCreateFromPlanPayload = {
  plan_id: number;
  title?: string;
};

export type ShoppingListMergePayload = {
  shopping_list_ids: number[];
  title?: string;
};

export type ShoppingListBulkDeletePayload = {
  shopping_list_ids: number[];
};

export type ShoppingListBulkDeleteResponse = {
  deleted_count: number;
};

export type ShoppingItemPatchPayload = {
  checked?: boolean;
  adjusted_grams?: DecimalString | null;
  excluded?: boolean;
  category?: FoodCategory;
  name_snapshot?: string;
  unit?: string;
};

export type ShoppingManualItemCreatePayload = {
  name: string;
  category?: FoodCategory;
  unit?: string;
  adjusted_grams?: DecimalString;
};
