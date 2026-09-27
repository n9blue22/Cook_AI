import { Sparkle } from 'lucide-react-native';
import { ActivityIndicator, Image, StyleSheet, Text, View } from 'react-native';
import { colors, fonts, onColor } from '../theme';

// Ảnh AI thật từ POST /recipes/{id}/image; url null = đang tạo.
export function AiDishImage({ url, name }: { url: string | null; name: string }) {
  return (
    <View style={st.frame}>
      {url === null ? (
        <View style={{ alignItems: 'center', gap: 10 }}>
          <ActivityIndicator color={colors.primary} />
          <Text style={st.loading}>Đang dựng ảnh minh hoạ…</Text>
        </View>
      ) : (
        <>
          <Image source={{ uri: url }} style={StyleSheet.absoluteFill} resizeMode="cover" accessibilityLabel={`Ảnh minh hoạ món ${name} do AI dựng`} />
          <View style={st.tag}>
            <Sparkle size={14} color={onColor} strokeWidth={TAG_ICON_STROKE} />
            <Text style={st.tagText}>Ảnh do AI dựng · minh hoạ</Text>
          </View>
        </>
      )}
    </View>
  );
}

const TAG_ICON_STROKE = 2; // RecipeImage.dc.html

const st = StyleSheet.create({
  frame: { height: 236, backgroundColor: '#F3ECE0', alignItems: 'center', justifyContent: 'center' },
  loading: { fontFamily: fonts.semibold, fontSize: 13, color: colors.muted },
  tag: {
    position: 'absolute',
    left: 14,
    bottom: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 14,
    backgroundColor: 'rgba(22, 21, 15, 0.82)',
  },
  tagText: { fontFamily: fonts.semibold, fontSize: 11.5, color: onColor },
});
