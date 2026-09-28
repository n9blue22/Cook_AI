// Công thức đã lưu trên server: danh sách cho màn Đã lưu (lọc theo ô tìm), toàn bộ danh sách (nút Lưu ở Recipe,
// "Món đã lưu gần đây" ở Main) — đều tra từ DB.
// Không lưu máy: khoá AsyncStorage dùng chung mọi tài khoản trên máy → user sau sẽ thấy món đã lưu của user trước
// (cache offline khoá theo user_id là TODO PWA, feature-spec §7 bước 11).
import { useCallback, useEffect, useRef, useState } from 'react';
import { isAuthRejection } from './api';
import type { Recipe } from './recipes';
import { deleteSaved, listSaved, saveRecipe, SavedRecipe } from './saved';
import type { PantryItem } from './userData';

const SAVED_AUTH_ERROR = 'Phiên đăng nhập đã hết hạn — đăng nhập lại để xem công thức đã lưu';
// Kết quả tìm cũ lưu máy trước khi có payload → không có công thức gốc để gửi lên.
const NOT_SAVABLE = 'Công thức này chưa lưu được — tìm lại công thức từ nguyên liệu rồi lưu';
const RECENT_COUNT = 3; // Main: "Món đã lưu gần đây"

type LoadStatus = 'idle' | 'loading' | 'ready' | 'error';
type SavedList = { status: LoadStatus; items: SavedRecipe[]; error: string | null };

// Lỗi mạng / 401 hiện rõ cho user, không thay bằng dữ liệu giả.
export const savedErrorText = (error: unknown) =>
  isAuthRejection(error) ? SAVED_AUTH_ERROR : error instanceof Error ? error.message : String(error);

export function useSavedRecipes(getAccessToken: () => Promise<string | null>, pantry: PantryItem[]) {
  const [savedList, setSavedList] = useState<SavedList>({ status: 'idle', items: [], error: null });
  // Toàn bộ món đã lưu (mới nhất trước, như server trả) — nguồn cho trạng thái nút Lưu và món gần đây.
  const [allSaved, setAllSaved] = useState<SavedList>({ status: 'idle', items: [], error: null });

  // Đọc qua ref để các hàm tải giữ nguyên identity (màn gọi trong effect) — tick/bỏ tick tủ không tải lại.
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
        if (!query.trim()) setAllSaved({ status: 'ready', items, error: null });
      } catch (error) {
        console.warn('Không tải được công thức đã lưu', error);
        // Bỏ danh sách cũ: đó là kết quả của ô tìm trước, hiện tiếp dưới ô tìm mới là sai.
        setSavedList({ status: 'error', items: [], error: savedErrorText(error) });
      }
    },
    [getAccessToken],
  );

  // Màn Recipe / Main: tải toàn bộ danh sách, không đụng danh sách đang lọc ở màn Đã lưu.
  const syncSaved = useCallback(async () => {
    setAllSaved((old) => ({ ...old, status: 'loading', error: null }));
    try {
      setAllSaved({ status: 'ready', items: await listSaved('', pantryIds.current, await getAccessToken()), error: null });
    } catch (error) {
      console.warn('Không tải được công thức đã lưu', error);
      setAllSaved((old) => ({ ...old, status: 'error', error: savedErrorText(error) }));
    }
  }, [getAccessToken]);

  const forget = (savedId: number) => {
    const drop = (old: SavedList) => ({ ...old, items: old.items.filter((x) => x.savedId !== savedId), error: null });
    setSavedList(drop);
    setAllSaved(drop);
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

  const findSaved = (recipeId: string) => allSaved.items.find((x) => x.recipe.id === recipeId);

  // Nút Lưu: đã lưu → DELETE, chưa → POST nguyên công thức đang xem. Lỗi → ném Error có câu hiển thị (useSubmit).
  const toggleSaved = async (recipe: Recipe) => {
    const existing = findSaved(recipe.id);
    try {
      const token = await getAccessToken();
      if (existing) {
        await deleteSaved(existing.savedId, token);
        forget(existing.savedId);
        return;
      }
      if (!recipe.payload) throw new Error(NOT_SAVABLE);
      const saved = await saveRecipe(recipe.payload, pantryIds.current, token);
      setAllSaved((old) => ({ ...old, items: [saved, ...old.items.filter((x) => x.recipe.id !== recipe.id)] }));
    } catch (error) {
      throw new Error(savedErrorText(error));
    }
  };

  return {
    savedList,
    loadSaved,
    removeSaved,
    syncSaved,
    toggleSaved,
    isSaved: (recipeId: string) => findSaved(recipeId) !== undefined,
    findSavedRecipe: (recipeId: string) => (savedList.items.find((x) => x.recipe.id === recipeId) ?? findSaved(recipeId))?.recipe,
    savedSyncError: allSaved.error, // trạng thái nút Lưu có thể sai → màn Recipe báo cho user
    recentSaved: { ...allSaved, items: allSaved.items.slice(0, RECENT_COUNT) },
  };
}
