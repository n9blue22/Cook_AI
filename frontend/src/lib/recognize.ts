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
// unlisted: tên AI thấy nhưng không có dòng riêng — không có trong danh mục, hoặc khớp gần đúng vào món đã có dòng.
export type ScanResult = { items: ScanItem[]; unlisted: string[] };

const UPLOAD_NAME = 'photo.jpg';
const UPLOAD_MIME = 'image/jpeg';

export function toScanResult(out: RecognizedOut): ScanResult {
  const items: ScanItem[] = out.accepted_ids.map((id) => ({ ingredientId: id, name: out.names[id], sure: true }));
  const unlisted: string[] = [];
  for (const { raw_name: seenAs, ingredient_id: id } of out.uncertain) {
    const taken = items.find((item) => item.ingredientId === id);
    if (id === null || taken) {
      // vd AI chưa chắc "dưa lưới", khớp gần đúng vào Dứa đã có dòng → vẫn cho user thấy AI đã nhìn ra gì.
      if (!taken || !sameName(seenAs, taken.name)) unlisted.push(seenAs);
      continue;
    }
    items.push({ ingredientId: id, name: out.names[id], sure: false, seenAs });
  }
  return { items, unlisted: [...unlisted, ...out.unmatched_names] };
}

const sameName = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

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
