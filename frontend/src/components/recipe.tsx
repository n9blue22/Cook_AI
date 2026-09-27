import { Check, ChevronRight, Plus, Utensils } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { formatPrice, Recipe } from '../lib/recipes';
import { artboard, colors, fonts, iconStroke, onColor } from '../theme';
import { Card, Chip, s as ui, Txt } from './ui';

// Chỉ hiện thông tin có thật — công thức từ API chưa có thời gian / độ khó / giá thì bỏ chip, không đoán.
export function MetaChips({ r, price = true }: { r: Recipe; price?: boolean }) {
  return (
    <View style={[ui.wrap, { gap: 7 }]}>
      {r.minutes !== undefined && <Chip small tone="alt" label={`${r.minutes} phút`} />}
      <Chip small tone="alt" label={`${r.serves} người`} />
      {r.level !== undefined && <Chip small tone="alt" label={r.level} />}
      {price && r.price !== undefined && <Chip small tone="alt" label={formatPrice(r.price)} />}
      {r.language === 'en' && <Chip small tone="alt" label="Bản gốc tiếng Anh" />}
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
  const n = r.nutrition;
  return (
    <Card style={{ gap: 14 }}>
      <View style={[ui.sectionHead, { gap: 8 }]}>
        {/* Không cắt chữ: màn hẹp thì cả hai xuống dòng (Recipe.dc.html) */}
        <Txt v="bodyStrong" style={{ flexShrink: 1 }}>Dinh dưỡng mỗi phần</Txt>
        <Text style={[st.macroLabel, { flexShrink: 1, fontFamily: fonts.semibold }]}>Nguồn: bảng thành phần thực phẩm</Text>
      </View>
      {n ? (
        <>
          <View style={[ui.row, { alignItems: 'baseline', gap: 8 }]}>
            <Txt v="display" style={{ lineHeight: 40 }}>{n.kcal}</Txt>
            <Text style={[st.macroLabel, { fontSize: 14, fontFamily: fonts.semibold }]}>kcal</Text>
          </View>
          <NutritionRow protein={n.protein} carbs={n.carbs} fat={n.fat} bars size={17} />
        </>
      ) : (
        // Không để AI tự sinh số (feature-spec mục 9): công thức gốc không ghi gram thì chưa tính được.
        <Txt v="caption" style={{ fontSize: 13 }}>Công thức này không ghi lượng theo gram nên chưa tính được dinh dưỡng.</Txt>
      )}
    </Card>
  );
}

export function IngredientRow({ name, amount, have }: { name: string; amount: string; have: boolean }) {
  const c = have ? colors.primary : colors.warn;
  const I = have ? Check : Plus;
  return (
    <View style={[ui.row, { gap: 10 }]}>
      <I size={INGREDIENT_ICON_SIZE} color={c} strokeWidth={INGREDIENT_ICON_STROKE} />
      <Text style={[st.ingName, !have && { color: colors.warn, fontFamily: fonts.semibold }]}>
        {name}
        {!have && <Text style={{ fontFamily: fonts.medium }}> — cần mua</Text>}
      </Text>
      <Text style={[st.ingAmt, !have && { color: colors.warn }]}>{amount}</Text>
    </View>
  );
}

// Xem trước các bước (Recipe.dc.html, Desktop.dc.html): quá STEP_PREVIEW_COUNT bước thì bước cuối hiện mờ,
// cắt 1 dòng để báo còn tiếp — đủ các bước nằm ở chế độ nấu (cook.tsx).
export function StepList({ steps }: { steps: { text: string }[] }) {
  const truncated = steps.length > STEP_PREVIEW_COUNT;
  const shown = truncated ? steps.slice(0, STEP_PREVIEW_COUNT) : steps;
  return (
    <View style={{ gap: 9 }}>
      {shown.map((step, i) => {
        const faded = truncated && i === shown.length - 1;
        return (
          <View key={i} style={{ flexDirection: 'row', gap: 12 }}>
            <View style={[st.stepNum, faded && { backgroundColor: colors.borderSoft }]}>
              <Text style={[st.stepNumText, faded && { color: colors.muted }]}>{i + 1}</Text>
            </View>
            <Text style={[st.stepText, faded && { color: colors.muted }]} numberOfLines={faded ? 1 : undefined}>
              {step.text}
            </Text>
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

const STEP_PREVIEW_COUNT = 3;
const INGREDIENT_ICON_SIZE = 17; // Recipe.dc.html
const INGREDIENT_ICON_STROKE = 2;

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
