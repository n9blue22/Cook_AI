// Công thức đã lưu trên server: GET /saved?q= (tìm theo tên, server lọc), DELETE /saved/{id}.
// Không import react-native: saved.test.mjs chạy thẳng bằng node.
import { apiRequest } from './api.ts';
import type { Diet, Recipe } from './recipes.ts';
import { type SuggestedRecipeOut, toRecipe } from './suggest.ts';

type SavedRecipeOut = {
  id: number;
  recipe_id: number;
  saved_at: string;
  diet_type: Diet | null; // tra từ bảng recipes; null khi món không còn đọc được
  recipe: SuggestedRecipeOut;
};

export type SavedRecipe = { savedId: number; savedAt: number; diet: Diet | null; recipe: Recipe };
export type SavedFilter = 'all' | 'quick' | 'veg';

const QUICK_MAX_MINUTES = 20;

// haveIds: nguyên liệu đang có trong tủ — để đánh dấu "cần mua" như công thức vừa tìm.
export const toSavedRecipe = (out: SavedRecipeOut, haveIds: number[]): SavedRecipe => ({
  savedId: out.id,
  savedAt: Date.parse(out.saved_at),
  diet: out.diet_type,
  recipe: toRecipe(out.recipe, haveIds),
});

// Món không ghi thời gian / không rõ chế độ ăn → không lọt vào "Nhanh" / "Chay" (không đoán).
export function matchesFilter(item: SavedRecipe, filter: SavedFilter): boolean {
  if (filter === 'quick') return item.recipe.minutes !== undefined && item.recipe.minutes < QUICK_MAX_MINUTES;
  if (filter === 'veg') return item.diet === 'vegetarian' || item.diet === 'vegan';
  return true;
}

export async function listSaved(query: string, haveIds: number[], token: string | null): Promise<SavedRecipe[]> {
  const q = query.trim();
  const out = await apiRequest<SavedRecipeOut[]>(q ? `/saved?q=${encodeURIComponent(q)}` : '/saved', { token });
  return out.map((item) => toSavedRecipe(item, haveIds));
}

export const deleteSaved = (savedId: number, token: string | null) =>
  apiRequest<void>(`/saved/${savedId}`, { method: 'DELETE', token });
