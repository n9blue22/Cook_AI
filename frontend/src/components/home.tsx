// Thẻ trên Main (Main.dc.html, Desktop.dc.html) đọc dữ liệu server: tủ lạnh, nhật ký hôm nay.
import { StyleSheet, Text, View } from 'react-native';
import { formatNum } from '../lib/recipes';
import { PantryItem, useStore } from '../lib/store';
import { artboard, colors, fonts } from '../theme';
import { NutritionRow } from './recipe';
import { Card, Chip, LinkText, s as ui, Txt } from './ui';

const chipLabel = (p: PantryItem) =>
  p.expiresDays !== undefined && p.expiresDays <= 2
    ? `${p.name} · còn ${p.expiresDays} ngày`
    : p.qty
      ? `${p.name} · ${p.qty}`
      : p.name;

// Sắp hết hạn → chip cảnh báo (chữ 600); còn lại chip trắng chữ 500 như Main.dc.html.
const fridgeChipStyle = (p: PantryItem) =>
  p.expiresDays !== undefined && p.expiresDays <= 2 ? ({ tone: 'warn' } as const) : ({ tone: 'default', medium: true } as const);

// Trạng thái tải dữ liệu server: đang tải / lỗi (có nút thử lại) / danh sách chip.
export function FridgeChips({ items }: { items: PantryItem[] }) {
  const { pantryError } = useStore();
  const pending = useLoadState('Đang tải tủ lạnh…');
  if (pending) return pending;
  return (
    <View style={{ gap: 8 }}>
      {items.length ? (
        <View style={ui.wrap}>
          {items.map((p) => (
            <Chip key={p.id} label={chipLabel(p)} {...fridgeChipStyle(p)} />
          ))}
        </View>
      ) : (
        <Txt v="caption">Chưa có nguyên liệu — chụp ảnh hoặc bấm Sửa để thêm.</Txt>
      )}
      {pantryError && <Txt v="caption" style={{ color: colors.danger }}>{pantryError}</Txt>}
    </View>
  );
}

// null = đã tải xong; còn lại là dòng "đang tải" hoặc lỗi kèm nút thử lại (không hiện số 0 như thật).
function useLoadState(loadingText: string) {
  const { userDataStatus, reloadUserData } = useStore();
  if (userDataStatus === 'ready') return null;
  if (userDataStatus !== 'error') return <Txt v="caption">{loadingText}</Txt>;
  return (
    <View style={[ui.row, { gap: 10, flexWrap: 'wrap' }]}>
      <Txt v="caption" style={{ color: colors.danger }}>Không tải được dữ liệu của bạn.</Txt>
      <LinkText label="Thử lại" onPress={reloadUserData} />
    </View>
  );
}

export function LogCard() {
  const { log, kcalGoal } = useStore();
  const pending = useLoadState('Đang tải nhật ký…');
  const pct = kcalGoal ? Math.min(100, Math.round((log.kcal / kcalGoal) * 100)) : 0;
  const left = kcalGoal ? kcalGoal - log.kcal : null;
  if (pending) return <Card>{pending}</Card>;
  return (
    <Card style={{ gap: 12 }}>
      <View style={[ui.row, { alignItems: 'flex-end', justifyContent: 'space-between' }]}>
        <View style={{ gap: 3 }}>
          <Txt v="overline" style={{ fontFamily: fonts.semibold, letterSpacing: 0.48 }}>Nhật ký hôm nay</Txt>
          <Text style={st.kcal}>
            {formatNum(log.kcal)}
            <Text style={st.kcalGoal}>{kcalGoal ? ` / ${formatNum(kcalGoal)} kcal` : ' kcal'}</Text>
          </Text>
        </View>
        {left === null ? (
          <Text style={[st.left, { color: colors.muted }]}>chưa đặt mục tiêu</Text>
        ) : (
          <Text style={[st.left, left < 0 && { color: colors.warn }]}>
            {left >= 0 ? `còn ${formatNum(left)}` : `vượt ${formatNum(-left)}`}
          </Text>
        )}
      </View>
      {kcalGoal !== null && (
        <View style={st.track} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: pct }}>
          <View style={[st.fill, { width: `${pct}%` }]} />
        </View>
      )}
      <NutritionRow protein={log.protein} carbs={log.carbs} fat={log.fat} labelFont={fonts.semibold} />
    </Card>
  );
}

const st = StyleSheet.create({
  kcal: { fontFamily: fonts.display, fontSize: 28, lineHeight: 28, color: colors.ink },
  kcalGoal: { fontFamily: fonts.medium, fontSize: 14, color: colors.muted },
  left: { fontFamily: fonts.semibold, fontSize: 12, color: colors.primary },
  track: { height: 8, borderRadius: 4, backgroundColor: artboard.track, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4, backgroundColor: colors.primary },
});
