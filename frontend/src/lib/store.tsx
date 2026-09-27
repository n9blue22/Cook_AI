import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth } from './auth';
import { recognizeImage, ScanResult } from './recognize';
import { AllergenSlug, Diet, findRecipes } from './recipes';
import { PantryRef, useUserData } from './userData';

export type { PantryItem } from './userData';

// Chỉ phần còn ở máy. Tủ lạnh, hồ sơ, nhật ký nằm trên server (useUserData).
type State = {
  saved: { id: string; savedAt: number }[];
  scan: ScanResult | null; // lần quét ảnh gần nhất; tách khỏi tủ lạnh để quét mới không xoá/ẩn món đã có
  cooking: { id: string; step: number } | null;
};

// Bộ lọc cho lần tìm công thức: mặc định lấy từ hồ sơ, sửa ở Confirm chỉ áp cho lần tìm đó.
type Filters = { diet: Diet; avoid: AllergenSlug[] };
const DEFAULT_FILTERS: Filters = { diet: 'omnivore', avoid: [] };
// ponytail: 8 món đã lưu như Saved.dc.html (mới nhất trước) — thay bằng GET /saved khi nối API.
const DAY_MS = 86_400_000;
const MOCK_SAVED_IDS = [
  'trung-chien-ca-chua', 'canh-chua-ca-loc', 'dau-hu-sot-ca', 'thit-kho-trung',
  'rau-muong-xao-toi', 'mi-xao-bo', 'sua-chua-chuoi', 'goi-cuon-chay',
];
const MOCK_SAVED_DAYS_AGO = [0, 3, 4, 6, 8, 11, 15, 20];
const mockSaved = () => MOCK_SAVED_IDS.map((id, k) => ({ id, savedAt: Date.now() - MOCK_SAVED_DAYS_AGO[k] * DAY_MS }));

const initial: State = {
  saved: mockSaved(),
  scan: null,
  cooking: null,
};

const KEY = 'bepai:v2'; // v1 còn chứa tủ lạnh / nhật ký mock — bỏ, không đọc lại

const sameName = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

function useStoreValue() {
  const [s, setS] = useState<State>(initial);
  const [ready, setReady] = useState(false);
  const [results, setResults] = useState<string[]>([]);
  const user = useUserData();
  const { getAccessToken } = useAuth();
  const [edited, setEdited] = useState<Filters | null>(null); // null = chưa sửa → theo hồ sơ
  const profileFilters = user.profile ? { diet: user.profile.diet_type, avoid: user.profile.allergens } : DEFAULT_FILTERS;
  const filters = edited ?? profileFilters;
  const setFilters = (next: (f: Filters) => Filters) => setEdited(next(filters));

  useEffect(() => {
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (raw) setS({ ...initial, ...(JSON.parse(raw) as Partial<State>) });
      })
      .catch((error: unknown) => console.warn('Không đọc được dữ liệu đã lưu trên máy', error))
      .finally(() => setReady(true));
  }, []);

  useEffect(() => {
    if (ready) AsyncStorage.setItem(KEY, JSON.stringify(s)).catch((error: unknown) => console.warn('Không ghi được dữ liệu trên máy', error));
  }, [s, ready]);

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
    // names: nguyên liệu dùng để tìm; mặc định mọi món đang tick trong tủ.
    search(names: string[] = user.pantry.filter((p) => p.checked).map((p) => p.name)) {
      const ids = findRecipes(names, filters.diet, filters.avoid).map((r) => r.id);
      setResults(ids);
      return ids;
    },
    toggleSaved: (id: string) =>
      set(({ saved }) => ({
        saved: saved.some((x) => x.id === id) ? saved.filter((x) => x.id !== id) : [{ id, savedAt: Date.now() }, ...saved],
      })),
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
    results,
    pantry: user.pantry,
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

// Gợi ý nhanh trên trang chủ, không đụng vào danh sách kết quả tìm kiếm.
export function useQuickPick() {
  const { pantry, diet, avoid } = useStore();
  return useMemo(
    () => findRecipes(pantry.filter((p) => p.checked).map((p) => p.name), diet, avoid),
    [pantry, diet, avoid],
  );
}
