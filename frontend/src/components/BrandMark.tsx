import { ChefHat } from 'lucide-react-native';
import { StyleProp, StyleSheet, Text, View, ViewStyle } from 'react-native';
import { colors, fonts, iconStroke, onColor } from '../theme';

// Logo + chữ "Chef AI" (sidebar desktop, màn đăng nhập).
export function BrandMark({ style, inverted }: { style?: StyleProp<ViewStyle>; inverted?: boolean }) {
  return (
    <View style={[st.brand, style]}>
      <View style={[st.logo, inverted && st.logoInverted]}>
        <ChefHat size={20} color={onColor} strokeWidth={iconStroke} />
      </View>
      <Text style={[st.brandText, inverted && st.brandTextInverted]}>Chef AI</Text>
    </View>
  );
}

const st = StyleSheet.create({
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  logo: { width: 34, height: 34, borderRadius: 11, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  logoInverted: { backgroundColor: 'rgba(255, 255, 255, 0.22)' },
  brandText: { fontFamily: fonts.display, fontSize: 19, color: colors.ink },
  brandTextInverted: { color: '#FFFFFF' },
});
