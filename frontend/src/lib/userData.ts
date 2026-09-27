// Dữ liệu riêng của user trên server: hồ sơ (GET /profile), tủ lạnh (/pantry), nhật ký hôm nay (GET /logs).
// Tải khi đăng nhập. StoreProvider remount theo email (app/_layout.tsx) → đổi user là state mới tinh,
// user sau không thấy dữ liệu user trước.
import { useCallback, useEffect, useState } from 'react';
import { ApiError, apiRequest, ApiOptions } from './api';
import { useAuth } from './auth';
import type { AllergenSlug, Diet } from './recipes';

type ProfileOut = { diet_type: Diet; daily_kcal_goal: number | null; allergens: AllergenSlug[] };
type PantryItemOut = {
  id: number;
  ingredient_id: number;
  name: string;
  quantity: number | null;
  unit: string | null;
  expires_on: string | null;
};
type DaySummaryOut = { date: string; kcal: number; protein_g: number; carb_g: number; fat_g: number; meals: number };

export type PantryItem = {
  id: number;
  name: string;
  qty?: string;
  expiresDays?: number;
  checked: boolean; // chọn để tìm công thức — chỉ ở máy, không lưu server
};
// Thêm vào tủ: theo ingredient_id (đã map sẵn, vd từ /recognize) hoặc theo tên user gõ (server tự map).
export type PantryRef = { ingredient_id: number } | { name: string };
export type DayLog = { kcal: number; protein: number; carbs: number; fat: number };
export type LoadStatus = 'idle' | 'loading' | 'ready' | 'error';

const DAY_MS = 86_400_000;
const EMPTY_LOG: DayLog = { kcal: 0, protein: 0, carbs: 0, fat: 0 };
const LOAD_ERROR = 'Không tải được dữ liệu của bạn';

// Ngày theo giờ máy (không dùng toISOString — đó là giờ UTC, trước 7h sáng ở VN sẽ lệch sang hôm qua).
export function localDate(d = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function daysUntil(isoDate: string): number {
  const [y, m, d] = isoDate.split('-').map(Number);
  const [ty, tm, td] = localDate().split('-').map(Number);
  return Math.round((Date.UTC(y, m - 1, d) - Date.UTC(ty, tm - 1, td)) / DAY_MS);
}

function toPantryItem(out: PantryItemOut, checked = true): PantryItem {
  const qty = out.quantity === null ? undefined : [out.quantity, out.unit].filter(Boolean).join(' ');
  return { id: out.id, name: out.name, qty, expiresDays: out.expires_on ? daysUntil(out.expires_on) : undefined, checked };
}

const toDayLog = (out: DaySummaryOut): DayLog => ({ kcal: out.kcal, protein: out.protein_g, carbs: out.carb_g, fat: out.fat_g });

const errorText = (error: unknown) => (error instanceof ApiError ? error.message : LOAD_ERROR);

export function useUserData() {
  const { status: authStatus, getAccessToken } = useAuth();
  const [status, setStatus] = useState<LoadStatus>('idle');
  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [pantry, setPantry] = useState<PantryItem[]>([]);
  const [log, setLog] = useState<DayLog>(EMPTY_LOG);
  const [pantryError, setPantryError] = useState<string | null>(null);

  const call = useCallback(
    async <T,>(path: string, options: Omit<ApiOptions, 'token'> = {}) =>
      apiRequest<T>(path, { ...options, token: await getAccessToken() }),
    [getAccessToken],
  );

  const fetchAll = useCallback(
    () =>
      Promise.all([
        call<ProfileOut>('/profile'),
        call<PantryItemOut[]>('/pantry'),
        call<DaySummaryOut>(`/logs?date=${localDate()}`),
      ]).then(
        ([p, items, day]) => {
          setProfile(p);
          setPantry((old) => items.map((i) => toPantryItem(i, old.find((o) => o.id === i.id)?.checked ?? true)));
          setLog(toDayLog(day));
          setStatus('ready');
        },
        (error: unknown) => {
          console.warn(LOAD_ERROR, error);
          setStatus('error');
        },
      ),
    [call],
  );

  useEffect(() => {
    if (authStatus === 'signedIn') void fetchAll();
  }, [authStatus, fetchAll]);

  const reload = useCallback(() => {
    setStatus('loading');
    void fetchAll();
  }, [fetchAll]);

  // Đã có thì server cập nhật dòng cũ. Lỗi → pantryError.
  const addPantryItems = useCallback(
    async (refs: PantryRef[]) => {
      setPantryError(null);
      const results = await Promise.allSettled(
        refs.map((body) => call<PantryItemOut>('/pantry', { method: 'POST', body })),
      );
      const added = results.flatMap((r) => (r.status === 'fulfilled' ? [toPantryItem(r.value)] : []));
      setPantry((old) => [...old.filter((o) => !added.some((a) => a.id === o.id)), ...added]);
      const failed = results.flatMap((r) => (r.status === 'rejected' ? [errorText(r.reason)] : []));
      if (failed.length) setPantryError(failed.join('\n'));
    },
    [call],
  );

  const removePantryItem = useCallback(
    async (id: number) => {
      setPantryError(null);
      try {
        await call<void>(`/pantry/${id}`, { method: 'DELETE' });
        setPantry((old) => old.filter((p) => p.id !== id));
      } catch (error) {
        console.warn('Xoá khỏi tủ thất bại', error);
        setPantryError(errorText(error));
      }
    },
    [call],
  );

  const togglePantryItem = useCallback(
    (id: number) => setPantry((old) => old.map((p) => (p.id === id ? { ...p, checked: !p.checked } : p))),
    [],
  );

  return { status, profile, pantry, log, pantryError, reload, addPantryItems, removePantryItem, togglePantryItem };
}
