import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useStore } from './store';
import { useSubmit } from './useSubmit';

const CAPTURE_QUALITY = 0.6; // backend còn thu nhỏ về 1024px, không cần ảnh gốc
const SCAN_FAILED = 'Không nhận diện được ảnh, thử lại';

// Ảnh → POST /recognize → mở Confirm. Lỗi (mất mạng, AI lỗi, ảnh không có đồ ăn) hiện cho user, không dùng dữ liệu giả.
export function useImageScan(navigate: 'push' | 'replace') {
  const { scanImage } = useStore();
  const { busy, error, run } = useSubmit(SCAN_FAILED);

  // getUri trả null = user huỷ, không làm gì.
  const scanFrom = (getUri: () => Promise<string | null>) =>
    run(async () => {
      const uri = await getUri();
      if (!uri) return;
      await scanImage(uri);
      router[navigate]({ pathname: '/confirm', params: { scan: '1' } });
    });

  const scanFromLibrary = () =>
    scanFrom(async () => {
      const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: CAPTURE_QUALITY });
      return res.canceled ? null : res.assets[0].uri;
    });

  return { busy, error, scanFrom, scanFromLibrary, captureQuality: CAPTURE_QUALITY };
}
