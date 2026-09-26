import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';
import { Allergen, Diet, findRecipes, getRecipe } from './recipes';

export type PantryItem = {
  name: string;
  qty?: string;
  expiresDays?: number;
  confidence?: number; // % từ AI nhận diện; undefined = người dùng tự nhập
  checked: boolean;
};

type State = {
  pantry: PantryItem[];
  diet: Diet;
  avoid: Allergen[];
  saved: { id: string; savedAt: number }[];
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
  log: { date: today(), ...MOCK_TODAY_LOG },
  cooking: null,
};

// ponytail: nhận diện giả lập — thay bằng gọi API vision khi nối AI.
const MOCK_DETECTED = [
  { name: 'Cà chua', confidence: 96 },
  { name: 'Trứng gà', confidence: 93 },
  { name: 'Hành lá', confidence: 71 },
];

const KEY = 'bepai:v1';

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
    applyDetection() {
      set(({ pantry }) => {
        const next = pantry.map((p) => ({ ...p }));
        for (const d of MOCK_DETECTED) {
          const hit = next.find((p) => p.name.toLowerCase() === d.name.toLowerCase());
          if (hit) hit.confidence = d.confidence;
          else next.push({ name: d.name, confidence: d.confidence, checked: d.confidence >= 80 });
        }
        return { pantry: next };
      });
      return MOCK_DETECTED;
    },
    toggleItem: (name: string) =>
      set(({ pantry }) => ({ pantry: pantry.map((p) => (p.name === name ? { ...p, checked: !p.checked } : p)) })),
    addItem(name: string) {
      const n = name.trim();
      if (!n) return;
      set(({ pantry }) =>
        pantry.some((p) => p.name.toLowerCase() === n.toLowerCase())
          ? { pantry }
          : { pantry: [...pantry, { name: n, checked: true }] },
      );
    },
    removeItem: (name: string) => set(({ pantry }) => ({ pantry: pantry.filter((p) => p.name !== name) })),
    setDiet: (diet: Diet) => set({ diet }),
    toggleAllergen: (a: Allergen) =>
      set(({ avoid }) => ({ avoid: avoid.includes(a) ? avoid.filter((x) => x !== a) : [...avoid, a] })),
    search() {
      const ids = findRecipes(
        s.pantry.filter((p) => p.checked).map((p) => p.name),
        s.diet,
        s.avoid,
      ).map((r) => r.id);
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
