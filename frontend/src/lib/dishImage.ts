// POST /recipes/{id}/image: ảnh AI minh hoạ món — backend sinh 1 lần rồi cache trong Storage theo recipe_id.
// Lỗi (429 hết lượt IMAGE_DAILY_CAP, 503 Cloudflare lỗi, 404) → ApiError với câu tiếng Việt từ backend, không có ảnh giả.
import { apiRequest } from './api.ts';

export type DishImageOut = { recipe_id: number; url: string; cached: boolean; note: string };

export const fetchDishImage = (recipeId: string, token: string | null): Promise<DishImageOut> =>
  apiRequest<DishImageOut>(`/recipes/${encodeURIComponent(recipeId)}/image`, { method: 'POST', token });
