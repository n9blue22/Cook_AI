import { ChefHat } from 'lucide-react-native';
import { StyleProp, StyleSheet, Text, View, ViewStyle } from 'react-native';
import { colors, fonts, iconStroke, onColor } from '../theme';

// Logo + chữ "Bếp AI" (sidebar desktop, màn đăng nhập).
export function BrandMark({ style }: { style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[st.brand, style]}>
      <View style={st.logo}>
        <ChefHat size={20} color={onColor} strokeWidth={iconStroke} />
      </View>
      <Text style={st.brandText}>Bếp AI</Text>
    </View>
  );
}

const st = StyleSheet.create({
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  logo: { width: 34, height: 34, borderRadius: 11, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  brandText: { fontFamily: fonts.display, fontSize: 19, color: colors.ink },
});
