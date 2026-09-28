import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, ReactNode, useContext, useEffect, useState } from 'react';
import { AuthStatus, useAuth } from './auth';
import { loadUserData, purgeUserData, userDataKey } from './localUserData';
import { recognizeImage, ScanResult } from './recognize';
import { AllergenSlug, Diet, Recipe } from './recipes';
import { suggestRecipes } from './suggest';
import { useSavedRecipes } from './useSavedRecipes';
import { PantryRef, useUserData } from './userData';

export type { PantryItem } from './userData';

// Bộ lọc cho lần tìm công thức: mặc định lấy từ hồ sơ, sửa ở Confirm chỉ áp cho lần tìm đó.
type Filters = { diet: Diet; avoid: AllergenSlug[] };
const DEFAULT_FILTERS: Filters = { diet: 'omnivore', avoid: [] };

// Chỉ phần còn ở máy (khoá theo user_id — localUserData.ts). Tủ lạnh, hồ sơ, nhật ký, công thức đã lưu (màn Đã lưu) nằm trên server.
type State = {
  scan: ScanResult | null; // lần quét ảnh gần nhất; tách khỏi tủ lạnh để quét mới không xoá/ẩn món đã có
  cooking: { id: string; step: number } | null;
  results: Recipe[]; // lần tìm gần nhất (/recipes/suggest) — lưu máy để tải lại trang / sang Cook vẫn còn
  searchedWith: Filters | null; // bộ lọc đã dùng cho results (user có thể đổi bộ lọc sau khi tìm)
};

const initial: State = {
  scan: null,
  cooking: null,
  results: [],
  searchedWith: null,
};

// Chỉ đọc dữ liệu của user đang đăng nhập, xoá của mọi user khác; đã đăng xuất → xoá hết.
// Đang khôi phục phiên ('loading') thì chưa biết user nào → không đọc, không xoá (xoá lúc này mất dữ liệu của chính user).
async function readLocalState(authStatus: AuthStatus, userId: string | null): Promise<string | null> {
  if (authStatus === 'loading') return null;
  if (userId) return loadUserData(AsyncStorage, userId);
  await purgeUserData(AsyncStorage);
  return null;
}

const sameName = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

function useStoreValue() {
  const [s, setS] = useState<State>(initial);
  const [ready, setReady] = useState(false);
  const user = useUserData();
  const { getAccessToken, userId, status: authStatus } = useAuth();
  const [edited, setEdited] = useState<Filters | null>(null); // null = chưa sửa → theo hồ sơ
  const savedRecipes = useSavedRecipes(getAccessToken, user.pantry);
  const profileFilters = user.profile ? { diet: user.profile.diet_type, avoid: user.profile.allergens } : DEFAULT_FILTERS;
  const filters = edited ?? profileFilters;
  const setFilters = (next: (f: Filters) => Filters) => setEdited(next(filters));

  // Store remount theo user_id + trạng thái đăng nhập (app/_layout.tsx).
  useEffect(() => {
    readLocalState(authStatus, userId)
      .then((raw) => {
        if (raw) setS({ ...initial, ...(JSON.parse(raw) as Partial<State>) });
      })
      .catch((error: unknown) => console.warn('Không đọc được dữ liệu đã lưu trên máy', error))
      .finally(() => setReady(true));
  }, [userId, authStatus]);

  useEffect(() => {
    if (!ready || !userId) return; // chưa đăng nhập → không ghi gì xuống máy
    AsyncStorage.setItem(userDataKey(userId), JSON.stringify(s)).catch((error: unknown) =>
      console.warn('Không ghi được dữ liệu trên máy', error),
    );
  }, [s, ready, userId]);

  const byName = (name: string) => user.pantry.find((p) => sameName(p.name, name));

  const set = (patch: Partial<State> | ((s: State) => Partial<State>)) =>
    setS((prev) => ({ ...prev, ...(typeof patch === 'function' ? patch(prev) : patch) }));

  const actions = {
    // Chỉ ghi lại kết quả quét; tủ lạnh chưa đổi cho tới khi user xác nhận ở Confirm (addConfirmed). Lỗi → ném ApiError.
    scanImage: async (uri: string) => set({ scan: await recognizeImage(uri, await getAccessToken()) }),
    // Món user đã xác nhận sau khi quét → bổ sung vào tủ (đã có thì server giữ dòng cũ). Không bao giờ xoá món khác.
    addConfirmed: (refs: PantryRef[]) => user.addPantryItems(refs),
    toggleItem(name: string) {
      const item = byName(name);
      if (item) user.togglePantryItem(item.id);
    },
    addItem(name: string) {
      const n = name.trim();
      if (n && !byName(n)) void user.addPantryItems([{ name: n }]);
    },
    removeItem(name: string) {
      const item = byName(name);
      if (item) void user.removePantryItem(item.id);
    },
    setDiet: (diet: Diet) => setFilters((f) => ({ ...f, diet })),
    toggleAllergen: (slugs: AllergenSlug[]) =>
      setFilters(({ diet, avoid }) => {
        const on = slugs.every((slug) => avoid.includes(slug));
        return { diet, avoid: on ? avoid.filter((x) => !slugs.includes(x)) : [...new Set([...avoid, ...slugs])] };
      }),
    // Lỗi (mất mạng, 429 hết lượt, lỗi server) → ném ApiError, giữ nguyên kết quả cũ.
    async suggest(ingredientIds: number[]) {
      const recipes = await suggestRecipes({ ingredientIds, ...filters }, await getAccessToken());
      set({ results: recipes, searchedWith: filters });
      return recipes;
    },
    // Công thức thật từ lần tìm gần nhất hoặc danh sách đã lưu.
    findRecipe: (id: string): Recipe | undefined => s.results.find((r) => r.id === id) ?? savedRecipes.findSavedRecipe(id),
    startCooking: (id: string) => set(({ cooking }) => ({ cooking: cooking?.id === id ? cooking : { id, step: 0 } })),
    setStep: (step: number) => set(({ cooking }) => ({ cooking: cooking && { ...cooking, step } })),
    // ponytail: công thức đang nấu vẫn là mock (id chữ, số dinh dưỡng tự đặt) — chưa ghi POST /logs để không đưa số
    // giả vào nhật ký thật. Nối khi Recipe/Cook dùng công thức thật từ /recipes/suggest (màn 4).
    finishCooking: () => set({ cooking: null }),
  };

  return {
    ...s,
    ...filters,
    ready,
    pantry: user.pantry,
    ...savedRecipes,
    log: user.log,
    kcalGoal: user.profile?.daily_kcal_goal ?? null,
    userDataStatus: user.status,
    pantryError: user.pantryError,
    reloadUserData: user.reload,
    ...actions,
  };
}

type Store = ReturnType<typeof useStoreValue>;
const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const v = useStoreValue();
  return <Ctx.Provider value={v}>{children}</Ctx.Provider>;
}

export function useStore() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useStore phải nằm trong StoreProvider');
  return v;
}

