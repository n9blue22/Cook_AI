// POST /recipes/suggest: nguyên liệu đã xác nhận + chế độ ăn + dị ứng → tối đa 5 công thức (AI chỉnh hoặc bản gốc).
// Chế độ ăn / dị ứng là bộ lọc cứng ở backend (WHERE), không phải gợi ý cho AI.
// Không import react-native: suggest.test.mjs chạy thẳng bằng node.
import { apiRequest } from './api.ts';
import type { AllergenSlug, Diet, Recipe, Step } from './recipes.ts';

type NutritionOut = { kcal: number; protein_g: number; carb_g: number; fat_g: number };
type StepOut = { step_no: number; action: string; temperature_c: number | null; duration_sec: number | null };
type IngredientOut = { ingredient_id: number; name: string; amount: number | null; unit: string | null };
export type SuggestedRecipeOut = {
  recipe_id: number;
  source: 'adapted' | 'original';
  title: string;
  servings: number;
  ingredients: IngredientOut[];
  steps: StepOut[];
  rest_sec: number;
  nutrition_per_serving: NutritionOut | null;
  has_unmapped_ingredients: boolean;
  unmapped_ingredients_warning: string | null;
  language: 'vi' | 'en';
  prep_minutes: number | null;
  raw_ingredient_note: string | null; // chỉ bản gốc không đạt ngưỡng nấu chín
};

export type SuggestQuery = { ingredientIds: number[]; diet: Diet; avoid: AllergenSlug[] };

const MAX_AMOUNT_DECIMALS = 2;

// Lượng + đơn vị theo kiểu Việt ("0,5 muỗng"); công thức gốc không ghi lượng → chỉ đơn vị hoặc để trống.
function formatAmount(amount: number | null, unit: string | null): string {
  const qty = amount === null ? '' : amount.toLocaleString('vi-VN', { maximumFractionDigits: MAX_AMOUNT_DECIMALS });
  return [qty, unit ?? ''].filter(Boolean).join(' ');
}

// Bước có cả nhiệt độ lẫn thời gian = bước nấu chín (cùng định nghĩa với validation backend) → chế độ nấu bắt chạy đủ giờ.
// ponytail: bước chưa gắn nguyên liệu nên mọi bước nấu đều bị giữ đủ giờ, kể cả luộc rau — gắn ingredient_id vào step nếu cần nới.
function toStep(out: StepOut): Step {
  const timerSec = out.duration_sec ?? undefined;
  const isCooking = out.temperature_c !== null && out.duration_sec !== null;
  return { text: out.action, timerSec, safetyMinSec: isCooking ? timerSec : undefined };
}

// haveIds: nguyên liệu user đã xác nhận có — để đánh dấu "cần mua" cho phần còn thiếu.
export function toRecipe(out: SuggestedRecipeOut, haveIds: number[]): Recipe {
  const n = out.nutrition_per_serving;
  return {
    id: String(out.recipe_id),
    name: out.title,
    serves: out.servings,
    minutes: out.prep_minutes ?? undefined,
    nutrition: n && { kcal: Math.round(n.kcal), protein: Math.round(n.protein_g), carbs: Math.round(n.carb_g), fat: Math.round(n.fat_g) },
    ingredients: out.ingredients.map((i) => ({
      key: String(i.ingredient_id),
      name: i.name,
      amount: formatAmount(i.amount, i.unit),
      have: haveIds.includes(i.ingredient_id),
    })),
    steps: [...out.steps].sort((a, b) => a.step_no - b.step_no).map(toStep),
    source: out.source,
    warning: out.unmapped_ingredients_warning,
    rawNote: out.raw_ingredient_note,
    language: out.language,
    restSec: out.rest_sec,
  };
}

export async function suggestRecipes(query: SuggestQuery, token: string | null): Promise<Recipe[]> {
  const body = { ingredient_ids: query.ingredientIds, diet_type: query.diet, allergens: query.avoid };
  const out = await apiRequest<SuggestedRecipeOut[]>('/recipes/suggest', { method: 'POST', body, token });
  return out.map((recipe) => toRecipe(recipe, query.ingredientIds));
}
