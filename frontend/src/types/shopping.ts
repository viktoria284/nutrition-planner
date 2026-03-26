import type { DecimalString } from "./plan";

export type ShoppingComputedItem = {
  food_id: number;
  name: string;
  brand: string | null;
  total_grams: DecimalString;
  checked: boolean;
  excluded?: boolean;
  adjusted_grams: DecimalString | null;
  effective_grams: DecimalString;
  is_manual: false;
};

export type ShoppingManualItem = {
  id: number;
  name: string;
  grams: DecimalString | null;
  unit: string | null;
  checked: boolean;
  created_at: string;
  updated_at: string;
  is_manual: true;
};

export type ShoppingListItem = ShoppingComputedItem | ShoppingManualItem;

export type ShoppingListRead = {
  items: ShoppingListItem[];
};

export type ShoppingItemPatchPayload = {
  checked?: boolean;
  adjusted_grams?: DecimalString | null;
  excluded?: boolean;
};

export type ShoppingManualItemCreatePayload = {
  name: string;
  grams?: DecimalString;
  unit?: string;
};
