import { router } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { Bookmark, BookmarkCheck, Camera, Copy, ImagePlus, UserRound } from 'lucide-react-native';
import { Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Clipboard from 'expo-clipboard';
import { PressState } from '../../components/BottomTabBar';
import { MetaChips, NutritionRow, RecipeRow, StepList } from '../../components/recipe';
import { Button, Card, Chip, IconButton, LinkText, SafetyBadge, Section, s as ui, Txt } from '../../components/ui';
import { ALLERGENS, DIETS, formatNum, haveIngredient, Recipe, recipeToText } from '../../lib/recipes';
import { PantryItem, useQuickPick, useStore } from '../../lib/store';
import { artboard, colors, DESKTOP_MIN, fonts, iconStroke, onColor } from '../../theme';

const QUICK_PICK_COUNT = 1; // Main.dc.html: 1 gợi ý nhanh
const WEEKDAYS = ['Chủ Nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy'];
const todayLabel = () => {
  const d = new Date();
  return `${WEEKDAYS[d.getDay()]}, ${d.getDate()} tháng ${d.getMonth() + 1}`;
};

const chipLabel = (p: PantryItem) =>
  p.expiresDays !== undefined && p.expiresDays <= 2
    ? `${p.name} · còn ${p.expiresDays} ngày`
    : p.qty
      ? `${p.name} · ${p.qty}`
      : p.name;

// Sắp hết hạn → chip cảnh báo (chữ 600); còn lại chip trắng chữ 500 như Main.dc.html.
const fridgeChipStyle = (p: PantryItem) =>
  p.expiresDays !== undefined && p.expiresDays <= 2 ? ({ tone: 'warn' } as const) : ({ tone: 'default', medium: true } as const);

export default function Home() {
  const desktop = useWindowDimensions().width >= DESKTOP_MIN;
  return desktop ? <HomeDesktop /> : <HomeMobile />;
}

function useHomeData() {
  const store = useStore();
  const picks = useQuickPick();
  const inFridge = store.pantry.filter((p) => p.checked);
  const names = inFridge.map((p) => p.name);
  const quickSub = (r: Recipe) =>
    `${r.minutes} phút · ${r.kcal} kcal · dùng ${r.ingredients.filter((i) => haveIngredient(names, i.key)).length}/${r.ingredients.length} nguyên liệu`;
  return { store, picks, inFridge, quickSub };
}

function HomeMobile() {
  const { store, picks, inFridge, quickSub } = useHomeData();
  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={[ui.scroll, { paddingTop: 28 }]} showsVerticalScrollIndicator={false}>
        <View style={[ui.row, { justifyContent: 'space-between', gap: 12 }]}>
          <View style={{ gap: 2, flexShrink: 1 }}>
            <Text style={st.date}>{todayLabel()}</Text>
            <Txt v="title">Tối nay nấu gì?</Txt>
          </View>
          {/* ponytail: chưa có màn hồ sơ (PATCH /profile) — nối onPress khi dựng màn đó */}
          <IconButton icon={UserRound} label="Hồ sơ cá nhân" />
        </View>

        <Pressable
          accessibilityRole="button"
          onPress={() => router.push('/camera')}
          style={({ pressed }) => [st.hero, pressed && { backgroundColor: colors.primaryDark, transform: [{ scale: 0.99 }] }]}
        >
          <View style={st.heroIcon}>
            <Camera size={26} color={onColor} strokeWidth={iconStroke} />
          </View>
          <View style={{ gap: 4, flex: 1 }}>
            <Text style={st.heroTitle}>Chụp nguyên liệu</Text>
            <Text style={st.heroSub}>Gợi ý món từ đồ bạn đang có</Text>
          </View>
        </Pressable>

        <Section title="Tủ lạnh của bạn" right={<LinkText label="Sửa" onPress={() => router.push('/confirm')} />}>
          {inFridge.length ? (
            <View style={ui.wrap}>
              {inFridge.map((p) => (
                <Chip key={p.name} label={chipLabel(p)} {...fridgeChipStyle(p)} />
              ))}
            </View>
          ) : (
            <Txt v="caption">Chưa có nguyên liệu — chụp ảnh hoặc bấm Sửa để thêm.</Txt>
          )}
        </Section>

        <LogCard />

        <Section title="Gợi ý nhanh">
          {picks.length ? (
            picks.slice(0, QUICK_PICK_COUNT).map((r) => (
              <RecipeRow key={r.id} r={r} sub={quickSub(r)} onPress={() => router.push({ pathname: '/recipe/[id]', params: { id: r.id } })} />
            ))
          ) : (
            <Txt v="caption">Không có món nào hợp bộ lọc hiện tại.</Txt>
          )}
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}

function LogCard() {
  const { log, kcalGoal } = useStore();
  const pct = Math.min(100, Math.round((log.kcal / kcalGoal) * 100));
  const left = kcalGoal - log.kcal;
  return (
    <Card style={{ gap: 12 }}>
      <View style={[ui.row, { alignItems: 'flex-end', justifyContent: 'space-between' }]}>
        <View style={{ gap: 3 }}>
          <Txt v="overline" style={{ fontFamily: fonts.semibold, letterSpacing: 0.48 }}>Nhật ký hôm nay</Txt>
          <Text style={st.kcal}>
            {formatNum(log.kcal)}
            <Text style={st.kcalGoal}> / {formatNum(kcalGoal)} kcal</Text>
          </Text>
        </View>
        <Text style={[st.left, left < 0 && { color: colors.warn }]}>
          {left >= 0 ? `còn ${formatNum(left)}` : `vượt ${formatNum(-left)}`}
        </Text>
      </View>
      <View style={st.track} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: pct }}>
        <View style={[st.fill, { width: `${pct}%` }]} />
      </View>
      <NutritionRow protein={log.protein} carbs={log.carbs} fat={log.fat} labelFont={fonts.semibold} />
    </Card>
  );
}

function HomeDesktop() {
  const { store, picks, inFridge } = useHomeData();
  const top = picks[0];
  const saved = top && store.saved.some((x) => x.id === top.id);
  const detected = store.pantry.filter((p) => p.confidence !== undefined);

  const pick = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.7 });
    if (res.canceled) return;
    store.applyDetection();
    router.push('/confirm');
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingVertical: 30, paddingHorizontal: 34, gap: 22 }}>
      <View style={[ui.row, { justifyContent: 'space-between', alignItems: 'flex-end' }]}>
        <View style={{ gap: 5 }}>
          <Text style={st.date}>{todayLabel()}</Text>
          <Txt v="title" style={{ fontSize: 30, lineHeight: 36 }}>Tối nay nấu gì?</Txt>
        </View>
        <Text style={[st.date, { fontFamily: fonts.semibold }]}>
          {formatNum(store.log.kcal)} / {formatNum(store.kcalGoal)} kcal hôm nay
        </Text>
      </View>

      <View style={{ flex: 1, flexDirection: 'row', gap: 24 }}>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ gap: 16 }} showsVerticalScrollIndicator={false}>
          <Pressable accessibilityRole="button" onPress={pick} style={({ hovered }: PressState) => [st.drop, hovered && { borderColor: colors.primary }]}>
            <View style={st.dropIcon}>
              <ImagePlus size={26} color={colors.primary} strokeWidth={iconStroke} />
            </View>
            <Txt v="item" style={{ fontSize: 16 }}>Chọn ảnh nguyên liệu</Txt>
            <Txt v="caption" style={{ fontSize: 13 }}>bấm để chọn ảnh · hoặc dùng webcam ở mục Chụp nguyên liệu</Txt>
          </Pressable>

          <Card style={{ gap: 14, padding: 18 }}>
            <Txt v="bodyStrong">
              {detected.length ? `AI nhận ra ${detected.length} nguyên liệu` : `Tủ lạnh có ${inFridge.length} nguyên liệu`}
            </Txt>
            <View style={ui.wrap}>
              {(detected.length ? detected : inFridge).map((p) =>
                p.confidence !== undefined ? (
                  <Chip key={p.name} label={`${p.name} · ${p.confidence}%`} tone={p.confidence >= 80 ? 'safe' : 'warn'} />
                ) : (
                  <Chip key={p.name} label={chipLabel(p)} />
                ),
              )}
            </View>
            <View style={{ height: 1, backgroundColor: colors.borderSoft }} />
            <View style={[ui.wrap, { alignItems: 'center' }]}>
              <Text style={[st.date, { fontFamily: fonts.bold }]}>Bộ lọc:</Text>
              <Chip small tone="safe" label={DIETS.find((d) => d.id === store.diet)!.label} />
              {store.avoid.map((a) => (
                <Chip key={a} small tone="danger" label={`Tránh ${ALLERGENS.find((x) => x.id === a)!.label.toLowerCase()}`} />
              ))}
              <LinkText label="Sửa" onPress={() => router.push('/confirm')} />
            </View>
          </Card>

          <SafetyBadge>
            Bộ lọc chế độ ăn và dị ứng được áp ngay ở bước truy vấn, nên công thức hiện ra đã loại sẵn món không phù hợp.
          </SafetyBadge>

          <LogCard />
        </ScrollView>

        <View style={{ flex: 1 }}>
          {top ? (
            <Card style={{ flex: 1, padding: 22, borderRadius: 22, gap: 16 }}>
              <View style={[ui.row, { justifyContent: 'space-between', alignItems: 'flex-start', gap: 14 }]}>
                <View style={{ gap: 8, flex: 1 }}>
                  <Txt v="overline" style={{ color: colors.primary, fontSize: 11.5 }}>Gợi ý 1 / {picks.length}</Txt>
                  <Txt v="title" style={{ fontSize: 27, lineHeight: 31 }}>{top.name}</Txt>
                </View>
                <View style={[ui.row, { gap: 8 }]}>
                  <IconButton square icon={Copy} label="Sao chép công thức" onPress={() => Clipboard.setStringAsync(recipeToText(top))} />
                  <IconButton square filled icon={saved ? BookmarkCheck : Bookmark} label={saved ? 'Bỏ lưu công thức' : 'Lưu công thức'} onPress={() => store.toggleSaved(top.id)} />
                </View>
              </View>
              <MetaChips r={top} />
              <View style={st.macroBox}>
                {[
                  ['Năng lượng', `${top.kcal}`],
                  ['Đạm', `${top.protein} g`],
                  ['Tinh bột', `${top.carbs} g`],
                  ['Béo', `${top.fat} g`],
                ].map(([k, v]) => (
                  <View key={k} style={{ flex: 1, gap: 3 }}>
                    <Text style={st.macroK}>{k}</Text>
                    <Text style={st.macroV}>{v}</Text>
                  </View>
                ))}
              </View>
              <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>
                <Section title="Cách nấu" gap={9}>
                  <StepList steps={top.steps} />
                </Section>
              </ScrollView>
              <View style={[ui.row, { gap: 10 }]}>
                <Button kind="secondary" label="Xem chi tiết" onPress={() => router.push({ pathname: '/recipe/[id]', params: { id: top.id } })} />
                <Button
                  style={{ flex: 1 }}
                  label="Bắt đầu nấu"
                  onPress={() => {
                    store.startCooking(top.id);
                    router.push('/cook');
                  }}
                />
              </View>
            </Card>
          ) : (
            <Card style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
              <Txt v="caption">Không có món nào hợp bộ lọc hiện tại.</Txt>
            </Card>
          )}
        </View>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  date: { fontFamily: fonts.medium, fontSize: 13, color: colors.muted, letterSpacing: 0.26 },
  hero: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    padding: 20,
    minHeight: 96,
    borderRadius: 22,
    backgroundColor: colors.primary,
  },
  heroIcon: { width: 52, height: 52, borderRadius: 26, backgroundColor: colors.primaryDark, alignItems: 'center', justifyContent: 'center' },
  heroTitle: { fontFamily: fonts.bold, fontSize: 19, color: onColor, letterSpacing: -0.2 },
  heroSub: { fontFamily: fonts.regular, fontSize: 13, color: artboard.onPrimaryMuted },
  kcal: { fontFamily: fonts.display, fontSize: 28, lineHeight: 28, color: colors.ink },
  kcalGoal: { fontFamily: fonts.medium, fontSize: 14, color: colors.muted },
  left: { fontFamily: fonts.semibold, fontSize: 12, color: colors.primary },
  track: { height: 8, borderRadius: 4, backgroundColor: artboard.track, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4, backgroundColor: colors.primary },
  drop: {
    height: 232,
    borderRadius: 22,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: artboard.dropLine,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  dropIcon: { width: 56, height: 56, borderRadius: 28, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  macroBox: { flexDirection: 'row', gap: 12, padding: 16, borderRadius: 16, backgroundColor: colors.bg },
  macroK: { fontFamily: fonts.bold, fontSize: 11, color: colors.muted },
  macroV: { fontFamily: fonts.bold, fontSize: 18, color: colors.ink },
});
