import { useRef, useState } from 'react';

// Trạng thái gửi form: chặn bấm 2 lần, gom lỗi thành câu hiển thị (backend đã viết sẵn tiếng Việt).
export function useSubmit(fallbackError: string) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Chặn bằng ref, không bằng state: 2 lần bấm trong cùng 1 nhịp render đều thấy busy=false cũ → gửi 2 lần
  // (đã tái hiện: "Đã nấu xong" bấm đúp ghi 2 bữa vào nhật ký).
  const inFlight = useRef(false);

  const run = async (action: () => Promise<void>) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      console.warn(fallbackError, e);
      setError(e instanceof Error ? e.message : fallbackError);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };

  return { busy, error, run };
}
