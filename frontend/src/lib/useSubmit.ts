import { useState } from 'react';

// Trạng thái gửi form: chặn bấm 2 lần, gom lỗi thành câu hiển thị (backend đã viết sẵn tiếng Việt).
export function useSubmit(fallbackError: string) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      console.warn(fallbackError, e);
      setError(e instanceof Error ? e.message : fallbackError);
    } finally {
      setBusy(false);
    }
  };

  return { busy, error, run };
}
