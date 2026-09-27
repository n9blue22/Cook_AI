// POST /recipes/{id}/image: ảnh AI minh hoạ món — backend sinh 1 lần rồi cache trong Storage theo recipe_id.
// regenerate = "Tạo lại": backend sinh bản riêng của user (không ghi đè ảnh dùng chung), tốn 1 lượt như lần đầu.
// title = tên món đang hiển thị (tên AI chỉnh); backend chỉ dùng nếu khớp nguyên liệu của công thức, không thì tên gốc.
// Lỗi (429 hết lượt IMAGE_DAILY_CAP, 503 Cloudflare lỗi, 404) → ApiError với câu tiếng Việt từ backend, không có ảnh giả.
import { apiRequest } from './api.ts';

export type DishImageOut = { recipe_id: number; url: string; cached: boolean; note: string };

export type DishImageQuery = { title: string; regenerate: boolean };

export const fetchDishImage = (recipeId: string, query: DishImageQuery, token: string | null): Promise<DishImageOut> =>
  apiRequest<DishImageOut>(`/recipes/${encodeURIComponent(recipeId)}/image`, { method: 'POST', body: query, token });
