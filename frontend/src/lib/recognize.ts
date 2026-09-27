// POST /recognize: ảnh → nguyên liệu để user xác nhận ở Confirm.
// Không import react-native: recognize.test.mjs chạy thẳng bằng node.
import { apiRequest } from './api.ts';

type RecognizedOut = {
  accepted_ids: number[];
  uncertain: { raw_name: string; ingredient_id: number | null }[];
  unmatched_names: string[];
  names: Record<string, string>; // ingredient_id → tên VI (JSON đổi key số thành chuỗi)
};

// sure=false: AI chưa chắc hoặc tên chỉ khớp gần đúng → không tự tick. seenAs: tên AI đọc được từ ảnh.
export type ScanItem = { ingredientId: number; name: string; sure: boolean; seenAs?: string };
export type ScanResult = { items: ScanItem[]; unmatched: string[] }; // unmatched: AI thấy nhưng chưa có trong danh mục

const UPLOAD_NAME = 'photo.jpg';
const UPLOAD_MIME = 'image/jpeg';

export function toScanResult(out: RecognizedOut): ScanResult {
  const sure = out.accepted_ids.map((id) => ({ ingredientId: id, name: out.names[id], sure: true }));
  const unsure = out.uncertain.flatMap((m) =>
    m.ingredient_id === null ? [] : [{ ingredientId: m.ingredient_id, name: out.names[m.ingredient_id], sure: false, seenAs: m.raw_name }],
  );
  // Nhiều tên AI đọc được có thể cùng map về 1 nguyên liệu → giữ dòng đầu (chắc chắn đứng trước).
  const items = [...sure, ...unsure].filter((item, i, all) => all.findIndex((o) => o.ingredientId === item.ingredientId) === i);
  return { items, unmatched: out.unmatched_names };
}

// Web: ảnh là data:/blob: URI → đổi thành Blob. Native: file:// → FormData của RN nhận thẳng {uri, name, type}.
async function imagePart(uri: string): Promise<Blob | { uri: string; name: string; type: string }> {
  if (uri.startsWith('data:') || uri.startsWith('blob:')) return (await fetch(uri)).blob();
  return { uri, name: UPLOAD_NAME, type: UPLOAD_MIME };
}

export async function recognizeImage(uri: string, token: string | null): Promise<ScanResult> {
  const form = new FormData();
  form.append('image', (await imagePart(uri)) as Blob, UPLOAD_NAME); // native: RN đọc {uri} dù kiểu khai là Blob
  return toScanResult(await apiRequest<RecognizedOut>('/recognize', { method: 'POST', body: form, token }));
}
