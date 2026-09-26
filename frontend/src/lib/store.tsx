import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';
import { Allergen, Diet, findRecipes, getRecipe } from './recipes';

export type PantryItem = {
  name: string;
  qty?: string;
  expiresDays?: number;
  checked: boolean; // đang có trong tủ (Main) — lần quét ảnh KHÔNG được đổi trường này về false
};

// Một nguyên liệu trong lần quét ảnh gần nhất; tách khỏi tủ lạnh để quét mới không xoá/ẩn món đã có.
export type ScanItem = { name: string; confidence: number };

type State = {
  pantry: PantryItem[];
  diet: Diet;
  avoid: Allergen[];
  saved: { id: string; savedAt: number }[];
  lastScan: ScanItem[];
  log: { date: string; kcal: number; protein: number; carbs: number; fat: number };
  cooking: { id: string; step: number } | null;
};

const KCAL_GOAL = 1800;
const today = () => new Date().toISOString().slice(0, 10);
const emptyLog = () => ({ date: today(), kcal: 0, protein: 0, carbs: 0, fat: 0 });
// ponytail: số liệu mock như Main.dc.html cho lần mở đầu — thay bằng GET /logs khi nối API.
const MOCK_TODAY_LOG = { kcal: 1240, protein: 62, carbs: 140, fat: 38 };

const initial: State = {
  pantry: [
    { name: 'Cà chua', qty: '3', checked: true },
    { name: 'Trứng gà', qty: '4', checked: true },
    { name: 'Hành lá', checked: true },
    { name: 'Thịt ba chỉ', expiresDays: 1, checked: true },
  ],
  diet: 'man',
  avoid: ['haisan'],
  saved: [],
  lastScan: [],
  log: { date: today(), ...MOCK_TODAY_LOG },
  cooking: null,
};

// % tối thiểu để tự tick nguyên liệu nhận diện được; thấp hơn → hiện "chưa chắc", user tự xác nhận.
export const MIN_CONFIDENT_PCT = 80;

// ponytail: nhận diện giả lập (Camera.dc.html) — Lệnh H thay bằng POST /api/v1/recognize.
export const MOCK_DETECTED: ScanItem[] = [
  { name: 'Cà chua', confidence: 96 },
  { name: 'Trứng gà', confidence: 93 },
  { name: 'Hành lá', confidence: 71 },
];

const KEY = 'bepai:v1';

const sameName = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

function useStoreValue() {
  const [s, setS] = useState<State>(initial);
  const [ready, setReady] = useState(false);
  const [results, setResults] = useState<string[]>([]);

  useEffect(() => {
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (!raw) return;
        const saved = JSON.parse(raw) as State;
        setS({ ...initial, ...saved, log: saved.log?.date === today() ? saved.log : emptyLog() });
      })
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);

  useEffect(() => {
    if (ready) AsyncStorage.setItem(KEY, JSON.stringify(s)).catch(() => {});
  }, [s, ready]);

  const set = (patch: Partial<State> | ((s: State) => Partial<State>)) =>
    setS((prev) => ({ ...prev, ...(typeof patch === 'function' ? patch(prev) : patch) }));

  const actions = {
    // Chỉ ghi lại kết quả quét; tủ lạnh chưa đổi cho tới khi user xác nhận ở Confirm (addConfirmed).
    applyDetection() {
      set({ lastScan: MOCK_DETECTED });
      return MOCK_DETECTED;
    },
    // Món user đã xác nhận sau khi quét → bổ sung vào tủ (đã có thì bật lại). Không bao giờ bỏ/xoá món khác.
    addConfirmed: (names: string[]) =>
      set(({ pantry }) => {
        const next = pantry.map((p) => (names.some((n) => sameName(n, p.name)) ? { ...p, checked: true } : p));
        const missing = names.filter((n) => !pantry.some((p) => sameName(n, p.name)));
        return { pantry: [...next, ...missing.map((name) => ({ name, checked: true }))] };
      }),
    toggleItem: (name: string) =>
      set(({ pantry }) => ({ pantry: pantry.map((p) => (p.name === name ? { ...p, checked: !p.checked } : p)) })),
    addItem(name: string) {
      const n = name.trim();
      if (!n) return;
      set(({ pantry }) =>
        pantry.some((p) => sameName(p.name, n))
          ? { pantry }
          : { pantry: [...pantry, { name: n, checked: true }] },
      );
    },
    removeItem: (name: string) => set(({ pantry }) => ({ pantry: pantry.filter((p) => p.name !== name) })),
    setDiet: (diet: Diet) => set({ diet }),
    toggleAllergen: (a: Allergen) =>
      set(({ avoid }) => ({ avoid: avoid.includes(a) ? avoid.filter((x) => x !== a) : [...avoid, a] })),
    // names: nguyên liệu dùng để tìm; mặc định mọi món đang tick trong tủ.
    search(names: string[] = s.pantry.filter((p) => p.checked).map((p) => p.name)) {
      const ids = findRecipes(names, s.diet, s.avoid).map((r) => r.id);
      setResults(ids);
      return ids;
    },
    toggleSaved: (id: string) =>
      set(({ saved }) => ({
        saved: saved.some((x) => x.id === id) ? saved.filter((x) => x.id !== id) : [{ id, savedAt: Date.now() }, ...saved],
      })),
    startCooking: (id: string) => set(({ cooking }) => ({ cooking: cooking?.id === id ? cooking : { id, step: 0 } })),
    setStep: (step: number) => set(({ cooking }) => ({ cooking: cooking && { ...cooking, step } })),
    finishCooking() {
      set(({ cooking, log }) => {
        const r = cooking && getRecipe(cooking.id);
        const l = log.date === today() ? log : emptyLog();
        if (!r) return { cooking: null };
        return {
          cooking: null,
          log: { ...l, kcal: l.kcal + r.kcal, protein: l.protein + r.protein, carbs: l.carbs + r.carbs, fat: l.fat + r.fat },
        };
      });
    },
  };

  return { ...s, ready, results, kcalGoal: KCAL_GOAL, ...actions };
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
