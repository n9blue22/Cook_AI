import { Check, ChevronRight, ShoppingBasket, Utensils } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { formatPrice, Recipe } from '../lib/recipes';
import { artboard, colors, fonts, iconStroke, onColor } from '../theme';
import { Card, Chip, s as ui, Txt } from './ui';

export function MetaChips({ r, price = true }: { r: Recipe; price?: boolean }) {
  return (
    <View style={[ui.wrap, { gap: 7 }]}>
      <Chip small tone="alt" label={`${r.minutes} phút`} />
      <Chip small tone="alt" label={`${r.serves} người`} />
      <Chip small tone="alt" label={r.level} />
      {price && <Chip small tone="alt" label={formatPrice(r.price)} />}
    </View>
  );
}

export function NutritionRow({
  protein,
  carbs,
  fat,
  bars,
  size = 15,
  labelFont = fonts.bold,
}: {
  protein: number;
  carbs: number;
  fat: number;
  bars?: boolean;
  size?: number;
  labelFont?: string; // Recipe.dc.html 700, Main.dc.html 600
}) {
  const items = [
    { label: 'Đạm', v: protein, c: colors.primary },
    { label: 'Tinh bột', v: carbs, c: artboard.carbs },
    { label: 'Béo', v: fat, c: artboard.fat },
  ];
  return (
    <View style={{ flexDirection: 'row', gap: 10 }}>
      {items.map((i) => (
        <View key={i.label} style={{ flex: 1, gap: bars ? 6 : 2 }}>
          <Text style={[st.macroLabel, { fontFamily: labelFont }]}>{i.label}</Text>
          <Text style={[st.macroVal, { fontSize: size }]}>{i.v} g</Text>
          {bars && <View style={{ height: 6, borderRadius: 3, backgroundColor: i.c }} />}
        </View>
      ))}
    </View>
  );
}

export function NutritionCard({ r }: { r: Recipe }) {
  return (
    <Card style={{ gap: 14 }}>
      <View style={[ui.sectionHead, { gap: 8 }]}>
        <Txt v="bodyStrong" numberOfLines={1}>Dinh dưỡng mỗi phần</Txt>
        <Text style={[st.macroLabel, { flexShrink: 1, textAlign: 'right' }]} numberOfLines={1}>
          Nguồn: bảng thành phần thực phẩm
        </Text>
      </View>
      <View style={[ui.row, { alignItems: 'baseline', gap: 8 }]}>
        <Txt v="display">{r.kcal}</Txt>
        <Text style={[st.macroLabel, { fontSize: 14 }]}>kcal</Text>
      </View>
      <NutritionRow protein={r.protein} carbs={r.carbs} fat={r.fat} bars size={17} />
    </Card>
  );
}

export function IngredientRow({ name, amount, have }: { name: string; amount: string; have: boolean }) {
  const c = have ? colors.primary : colors.warn;
  const I = have ? Check : ShoppingBasket;
  return (
    <View style={[ui.row, { gap: 10, minHeight: 28 }]}>
      <I size={18} color={c} strokeWidth={iconStroke} />
      <Text style={[st.ingName, !have && { color: colors.warn, fontFamily: fonts.semibold }]}>
        {name}
        {!have && <Text style={{ fontFamily: fonts.medium }}> — cần mua</Text>}
      </Text>
      <Text style={[st.ingAmt, !have && { color: colors.warn }]}>{amount}</Text>
    </View>
  );
}

export function StepList({ steps }: { steps: { text: string }[] }) {
  return (
    <View style={{ gap: 9 }}>
      {steps.map((st_, i) => {
        return (
          <View key={i} style={{ flexDirection: 'row', gap: 12 }}>
            <View style={st.stepNum}>
              <Text style={st.stepNumText}>{i + 1}</Text>
            </View>
            <Text style={st.stepText}>{st_.text}</Text>
          </View>
        );
      })}
    </View>
  );
}

export function RecipeRow({ r, sub, onPress }: { r: Recipe; sub: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [st.row, pressed && { opacity: 0.85 }]}
    >
      <View style={ui.thumb}>
        <Utensils size={24} color={colors.muted} strokeWidth={iconStroke} />
      </View>
      <View style={{ flex: 1, gap: 4 }}>
        <Txt v="item">{r.name}</Txt>
        <Txt v="caption" style={{ fontFamily: fonts.medium }}>{sub}</Txt>
      </View>
      <ChevronRight size={20} color={colors.muted} strokeWidth={iconStroke} />
    </Pressable>
  );
}

const st = StyleSheet.create({
  macroLabel: { fontFamily: fonts.bold, fontSize: 11, color: colors.muted },
  macroVal: { fontFamily: fonts.bold, color: colors.ink },
  ingName: { flex: 1, fontFamily: fonts.medium, fontSize: 14, color: colors.ink },
  ingAmt: { fontFamily: fonts.semibold, fontSize: 14, color: colors.muted },
  stepNum: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  stepNumText: { fontFamily: fonts.bold, fontSize: 12, color: onColor },
  stepText: { flex: 1, fontFamily: fonts.medium, fontSize: 14, lineHeight: 21, color: colors.ink },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    padding: 12,
    borderRadius: 18,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
});
