import { Sparkles } from 'lucide-react-native';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import Svg, { Ellipse, Path, Rect } from 'react-native-svg';
import { colors, fonts, iconStroke, onColor } from '../theme';

// ponytail: ảnh minh hoạ tĩnh lấy từ artboard; thay bằng ảnh từ API tạo ảnh khi nối AI.
export function AiDishImage({ loading, name }: { loading: boolean; name: string }) {
  return (
    <View style={st.frame}>
      {loading ? (
        <View style={{ alignItems: 'center', gap: 10 }}>
          <ActivityIndicator color={colors.primary} />
          <Text style={st.loading}>Đang dựng ảnh minh hoạ…</Text>
        </View>
      ) : (
        <>
          <Svg width="100%" height="100%" viewBox="0 0 350 236" preserveAspectRatio="xMidYMid slice" accessibilityLabel={`Ảnh minh hoạ món ${name} do AI dựng`}>
            <Rect width="350" height="236" fill="#F3ECE0" />
            <Path d="M150 34c0-9 9-11 9-19 0-5-3-8-3-8" fill="none" stroke="#D9CFBC" strokeWidth="3" strokeLinecap="round" />
            <Path d="M178 28c0-9 9-11 9-19 0-5-3-8-3-8" fill="none" stroke="#D9CFBC" strokeWidth="3" strokeLinecap="round" />
            <Path d="M206 34c0-9 9-11 9-19 0-5-3-8-3-8" fill="none" stroke="#D9CFBC" strokeWidth="3" strokeLinecap="round" />
            <Ellipse cx="175" cy="140" rx="126" ry="82" fill="#FFFDF7" stroke="#E5DCC9" strokeWidth="2" />
            <Ellipse cx="175" cy="140" rx="100" ry="62" fill="#FBF5E8" stroke="#EFE5D2" strokeWidth="2" />
            <Ellipse cx="139" cy="141" rx="35" ry="25" fill="#F2CB6A" />
            <Ellipse cx="184" cy="127" rx="30" ry="21" fill="#E8B84B" />
            <Ellipse cx="205" cy="154" rx="27" ry="19" fill="#F2CB6A" />
            <Ellipse cx="160" cy="160" rx="24" ry="16" fill="#E8B84B" />
            <Path d="M126 119c10-7 24-5 30 4 5 8-1 18-12 20-12 2-23-4-25-12-1-6 2-9 7-12z" fill="#C4462A" />
            <Path d="M196 106c11-4 22 2 24 11 2 9-7 16-17 15-11-1-19-8-18-16 1-6 5-8 11-10z" fill="#D65C39" />
            <Path d="M181 166c10-5 22 0 24 9 2 8-6 15-16 14-10-1-18-7-17-14 1-5 4-7 9-9z" fill="#C4462A" />
            <Path d="M116 155c8-3 15 1 16 7 1 6-5 10-12 9-7 0-12-5-11-10 0-3 3-5 7-6z" fill="#D65C39" />
            <Rect x="146" y="106" width="16" height="5" rx="2.5" transform="rotate(-16 146 106)" fill="#4E8A4B" />
            <Rect x="196" y="140" width="18" height="5" rx="2.5" transform="rotate(12 196 140)" fill="#4E8A4B" />
            <Rect x="153" y="176" width="15" height="5" rx="2.5" transform="rotate(-8 153 176)" fill="#5C9B58" />
            <Rect x="212" y="120" width="13" height="4.5" rx="2.2" transform="rotate(24 212 120)" fill="#5C9B58" />
          </Svg>
          <View style={st.tag}>
            <Sparkles size={14} color={onColor} strokeWidth={iconStroke} />
            <Text style={st.tagText}>Ảnh do AI dựng · minh hoạ</Text>
          </View>
        </>
      )}
    </View>
  );
}

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
