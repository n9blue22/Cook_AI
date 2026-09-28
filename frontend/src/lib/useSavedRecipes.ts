// Công thức đã lưu trên server: danh sách cho màn Đã lưu + trạng thái nút Lưu (recipe id → savedId, tra từ DB).
// Không lưu máy: khoá AsyncStorage dùng chung mọi tài khoản trên máy → user sau sẽ thấy món đã lưu của user trước
// (cache offline khoá theo user_id là TODO PWA, feature-spec §7 bước 11).
import { useCallback, useEffect, useRef, useState } from 'react';
import { isAuthRejection } from './api';
import type { Recipe } from './recipes';
import { deleteSaved, listSaved, saveRecipe, SavedRecipe } from './saved';
import type { PantryItem } from './userData';

const SAVED_AUTH_ERROR = 'Phiên đăng nhập đã hết hạn — đăng nhập lại để xem công thức đã lưu';
// Món mẫu (mock) hoặc kết quả tìm cũ lưu máy trước khi có payload → không có công thức gốc để gửi lên.
const NOT_SAVABLE = 'Công thức này chưa lưu được — tìm lại công thức từ nguyên liệu rồi lưu';

type SavedList = { status: 'idle' | 'loading' | 'ready' | 'error'; items: SavedRecipe[]; error: string | null };
type SavedIds = Record<string, number>; // recipe id → savedId (id dòng saved_recipes, dùng để DELETE)

// Lỗi mạng / 401 hiện rõ cho user, không thay bằng dữ liệu giả.
const savedErrorText = (error: unknown) =>
  isAuthRejection(error) ? SAVED_AUTH_ERROR : error instanceof Error ? error.message : String(error);

const indexByRecipe = (items: SavedRecipe[]): SavedIds => Object.fromEntries(items.map((x) => [x.recipe.id, x.savedId]));

export function useSavedRecipes(getAccessToken: () => Promise<string | null>, pantry: PantryItem[]) {
  const [savedList, setSavedList] = useState<SavedList>({ status: 'idle', items: [], error: null });
  const [savedIds, setSavedIds] = useState<SavedIds>({});

  // Đọc qua ref để loadSaved giữ nguyên identity (màn Đã lưu gọi nó trong effect) — tick/bỏ tick tủ không tải lại.
  const pantryIds = useRef<number[]>([]);
  useEffect(() => {
    pantryIds.current = pantry.map((p) => p.ingredientId);
  }, [pantry]);

  const loadSaved = useCallback(
    async (query: string) => {
      setSavedList((old) => ({ ...old, status: 'loading', error: null }));
      try {
        const items = await listSaved(query, pantryIds.current, await getAccessToken());
        setSavedList({ status: 'ready', items, error: null });
        if (!query.trim()) setSavedIds(indexByRecipe(items)); // chỉ danh sách đầy đủ mới biết món nào CHƯA lưu
      } catch (error) {
        console.warn('Không tải được công thức đã lưu', error);
        // Bỏ danh sách cũ: đó là kết quả của ô tìm trước, hiện tiếp dưới ô tìm mới là sai.
        setSavedList({ status: 'error', items: [], error: savedErrorText(error) });
      }
    },
    [getAccessToken],
  );

  // Màn Recipe / Main: đồng bộ trạng thái nút Lưu với DB, không đụng danh sách đang lọc ở màn Đã lưu. Lỗi → ném.
  const syncSavedIds = useCallback(async () => {
    setSavedIds(indexByRecipe(await listSaved('', [], await getAccessToken())));
  }, [getAccessToken]);

  const forget = (savedId: number) => {
    setSavedList((old) => ({ ...old, items: old.items.filter((x) => x.savedId !== savedId), error: null }));
    setSavedIds((ids) => Object.fromEntries(Object.entries(ids).filter(([, id]) => id !== savedId)));
  };

  const removeSaved = useCallback(
    async (savedId: number) => {
      try {
        await deleteSaved(savedId, await getAccessToken());
        forget(savedId);
      } catch (error) {
        console.warn('Bỏ lưu công thức thất bại', error);
        setSavedList((old) => ({ ...old, error: savedErrorText(error) }));
      }
    },
    [getAccessToken],
  );

  // Nút Lưu: đã lưu → DELETE, chưa → POST nguyên công thức đang xem. Lỗi → ném Error có câu hiển thị (useSubmit).
  const toggleSaved = async (recipe: Recipe) => {
    const token = await getAccessToken();
    const savedId = savedIds[recipe.id];
    try {
      if (savedId !== undefined) {
        await deleteSaved(savedId, token);
        forget(savedId);
        return;
      }
      if (!recipe.payload) throw new Error(NOT_SAVABLE);
      const newId = await saveRecipe(recipe.payload, token);
      setSavedIds((ids) => ({ ...ids, [recipe.id]: newId }));
    } catch (error) {
      throw new Error(savedErrorText(error));
    }
  };

  const isSaved = (recipeId: string) => savedIds[recipeId] !== undefined;

  return { savedList, loadSaved, removeSaved, syncSavedIds, toggleSaved, isSaved };
}
