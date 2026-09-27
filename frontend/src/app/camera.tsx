import { CameraView, useCameraPermissions } from 'expo-camera';
import { router } from 'expo-router';
import { Camera, ChevronLeft, Image as ImageIcon, TextAlignStart, Zap, ZapOff } from 'lucide-react-native';
import { useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, IconButton } from '../components/ui';
import { useImageScan } from '../lib/useImageScan';
import { artboard, colors, fonts, iconStroke, onColor } from '../theme';

const SIDE_ICON_SIZE = 22; // Camera.dc.html
const CAPTURE_FAILED = 'Không chụp được ảnh — thử lại hoặc chọn ảnh từ thư viện';

export default function CameraScreen() {
  const [perm, requestPerm] = useCameraPermissions();
  const cam = useRef<CameraView>(null);
  const [torch, setTorch] = useState(false);
  const { busy, error, scanFrom, scanFromLibrary, captureQuality } = useImageScan('replace');

  const shoot = () =>
    scanFrom(async () => {
      try {
        const photo = await cam.current?.takePictureAsync({ quality: captureQuality });
        if (photo) return photo.uri;
      } catch (captureError) {
        console.warn('Không chụp được ảnh', captureError);
      }
      throw new Error(CAPTURE_FAILED);
    });

  const back = () => (router.canGoBack() ? router.back() : router.replace('/'));

  return (
    <SafeAreaView edges={['top']} style={st.root}>
      <View style={st.header}>
        <IconButton dark icon={ChevronLeft} label="Quay lại" onPress={back} />
        <Text style={st.title}>Chụp nguyên liệu</Text>
        <IconButton dark icon={torch ? ZapOff : Zap} label={torch ? 'Tắt đèn flash' : 'Bật đèn flash'} onPress={() => setTorch((t) => !t)} />
      </View>

      <View style={st.frame}>
        {perm?.granted && <CameraView ref={cam} style={StyleSheet.absoluteFill} facing="back" enableTorch={torch} />}

        <View style={st.cornersRow}>
          <View style={[st.corner, { borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 14 }]} />
          <View style={[st.corner, { borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 14 }]} />
        </View>

        <View style={{ alignItems: 'center', gap: 14 }}>
          {perm && !perm.granted && !busy && !error ? ( // chọn ảnh thư viện không cần quyền camera → vẫn hiện trạng thái
            <View style={{ alignItems: 'center', gap: 12, paddingHorizontal: 10 }}>
              <View style={st.hint}>
                <Text style={st.hintText}>Cần quyền camera để nhận diện nguyên liệu</Text>
              </View>
              {perm.canAskAgain !== false && <Button size="md" label="Cho phép camera" onPress={requestPerm} />}
            </View>
          ) : (
            <ScanStatus busy={busy} error={error} />
          )}
        </View>

        <View style={st.cornersRow}>
          <View style={[st.corner, { borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 14 }]} />
          <View style={[st.corner, { borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 14 }]} />
        </View>
      </View>

      <Text style={st.caption}>Chụp được nhiều nguyên liệu cùng lúc · AI nhận diện sau khi chụp</Text>

      <View style={st.controls}>
        <Pressable accessibilityRole="button" accessibilityLabel="Chọn ảnh từ thư viện" onPress={scanFromLibrary} disabled={busy} style={({ pressed }) => [st.side, (pressed || busy) && { opacity: 0.7 }]}>
          <ImageIcon size={SIDE_ICON_SIZE} color={artboard.cam.ink} strokeWidth={iconStroke} />
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Chụp ảnh"
          onPress={shoot}
          disabled={busy}
          style={({ pressed }) => [st.shutter, pressed && { transform: [{ scale: 0.94 }] }, busy && { opacity: 0.6 }]}
        >
          <Camera size={30} color={colors.primary} strokeWidth={iconStroke} />
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Nhập nguyên liệu bằng tay"
          onPress={() => router.replace({ pathname: '/confirm', params: { add: '1' } })}
          disabled={busy}
          style={({ pressed }) => [st.side, (pressed || busy) && { opacity: 0.7 }]}
        >
          <TextAlignStart size={SIDE_ICON_SIZE} color={artboard.cam.ink} strokeWidth={iconStroke} />
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

// Lỗi hiện ngay trên khung; bấm chụp / chọn ảnh lại là thử lại.
function ScanStatus({ busy, error }: { busy: boolean; error: string | null }) {
  const failed = !busy && error !== null;
  const text = busy ? 'Đang nhận diện nguyên liệu…' : (error ?? 'Đưa toàn bộ nguyên liệu vào khung');
  return (
    <View style={[st.hint, failed && { backgroundColor: colors.warnBg }]} accessibilityLiveRegion="polite" accessibilityRole={failed ? 'alert' : undefined}>
      {busy && <ActivityIndicator color={artboard.cam.ink} />}
      <Text style={[st.hintText, failed && { color: colors.warn }]}>{text}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.camBg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 24, paddingBottom: 14 },
  title: { fontFamily: fonts.semibold, fontSize: 15, color: onColor },
  frame: {
    flex: 1,
    marginHorizontal: 20,
    borderRadius: 26,
    backgroundColor: colors.camSurface,
    overflow: 'hidden',
    padding: 22,
    justifyContent: 'space-between',
  },
  cornersRow: { flexDirection: 'row', justifyContent: 'space-between' },
  corner: { width: 40, height: 40, borderColor: artboard.cam.ink },
  hint: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 9,
    paddingHorizontal: 16,
    borderRadius: 18,
    backgroundColor: 'rgba(20, 22, 15, 0.72)',
  },
  hintText: { flexShrink: 1, fontFamily: fonts.semibold, fontSize: 13, color: artboard.cam.ink, textAlign: 'center' },
  caption: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 10, textAlign: 'center', fontFamily: fonts.medium, fontSize: 12, color: artboard.cam.dim },
  controls: { height: 168, paddingHorizontal: 28, paddingBottom: 34, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  side: {
    width: 56,
    height: 56,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: artboard.cam.line,
    backgroundColor: colors.camSurface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  shutter: {
    // Artboard ghi 84px nhưng thiếu box-sizing → viền 5px cộng ra ngoài, hiển thị thật 94px.
    width: 94,
    height: 94,
    borderRadius: 47,
    backgroundColor: onColor,
    borderWidth: 5,
    borderColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
