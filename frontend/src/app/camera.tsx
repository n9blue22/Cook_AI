import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { Camera, ChevronLeft, Image as ImageIcon, TextAlignStart, Zap, ZapOff } from 'lucide-react-native';
import { useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, IconButton } from '../components/ui';
import { MIN_CONFIDENT_PCT, MOCK_DETECTED, useStore } from '../lib/store';
import { artboard, colors, fonts, iconStroke, onColor } from '../theme';

const CAPTURE_QUALITY = 0.6;
const SIDE_ICON_SIZE = 22; // Camera.dc.html

export default function CameraScreen() {
  const [perm, requestPerm] = useCameraPermissions();
  const { applyDetection } = useStore();
  const cam = useRef<CameraView>(null);
  const [torch, setTorch] = useState(false);
  const [busy, setBusy] = useState(false);

  // Mock: chip hiện sẵn trên khung như artboard; ảnh chụp chưa gửi đi đâu (Lệnh H nối /recognize).
  const goConfirm = () => {
    applyDetection();
    router.replace({ pathname: '/confirm', params: { scan: '1' } });
  };

  const shoot = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await cam.current?.takePictureAsync({ quality: CAPTURE_QUALITY });
    } catch (error) {
      // Web / máy không có camera: vẫn đi tiếp với dữ liệu mock, nhưng ghi lại để biết.
      console.warn('Không chụp được ảnh, dùng dữ liệu mock', error);
    }
    goConfirm();
  };

  const pickFromLibrary = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: CAPTURE_QUALITY });
    if (!res.canceled) goConfirm();
  };

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
          {perm && !perm.granted ? (
            <View style={{ alignItems: 'center', gap: 12, paddingHorizontal: 10 }}>
              <Text style={st.hint}>Cần quyền camera để nhận diện nguyên liệu</Text>
              {perm.canAskAgain !== false && <Button size="md" label="Cho phép camera" onPress={requestPerm} />}
            </View>
          ) : (
            <>
              <Text style={st.hint}>Đưa toàn bộ nguyên liệu vào khung</Text>
              <View style={st.chips}>
                {MOCK_DETECTED.map((c) => {
                  const low = c.confidence < MIN_CONFIDENT_PCT;
                  return (
                    <View key={c.name} style={[st.chip, low && { backgroundColor: artboard.cam.lowChip }]}>
                      <Text style={[st.chipText, low && { color: artboard.cam.ink }]}>
                        {c.name} · {c.confidence}%
                      </Text>
                    </View>
                  );
                })}
              </View>
            </>
          )}
        </View>

        <View style={st.cornersRow}>
          <View style={[st.corner, { borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 14 }]} />
          <View style={[st.corner, { borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 14 }]} />
        </View>
      </View>

      <Text style={st.caption}>Chụp được nhiều nguyên liệu cùng lúc · nhận diện ngay trên khung hình</Text>

      <View style={st.controls}>
        <Pressable accessibilityRole="button" accessibilityLabel="Chọn ảnh từ thư viện" onPress={pickFromLibrary} style={({ pressed }) => [st.side, pressed && { opacity: 0.7 }]}>
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
          style={({ pressed }) => [st.side, pressed && { opacity: 0.7 }]}
        >
          <TextAlignStart size={SIDE_ICON_SIZE} color={artboard.cam.ink} strokeWidth={iconStroke} />
        </Pressable>
      </View>
    </SafeAreaView>
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
    paddingVertical: 9,
    paddingHorizontal: 16,
    borderRadius: 18,
    backgroundColor: 'rgba(20, 22, 15, 0.72)',
    fontFamily: fonts.semibold,
    fontSize: 13,
    color: artboard.cam.ink,
    textAlign: 'center',
    overflow: 'hidden',
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' },
  chip: { paddingVertical: 8, paddingHorizontal: 13, borderRadius: 16, backgroundColor: colors.primary },
  chipText: { fontFamily: fonts.semibold, fontSize: 13, color: onColor },
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
