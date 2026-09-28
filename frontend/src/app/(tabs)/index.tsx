import { router, useFocusEffect } from 'expo-router';
import { Bookmark, Camera, ImagePlus } from 'lucide-react-native';
import { useCallback } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AccountButton } from '../../components/AccountButton';
import { FridgeChips, LogCard } from '../../components/home';
import { PressState } from '../../components/BottomTabBar';
import { RecipeRow } from '../../components/recipe';
import { Button, Card, Chip, LinkText, SafetyBadge, Section, s as ui, Txt } from '../../components/ui';
import { avoidLabels, dietLabel, formatNum } from '../../lib/recipes';
import { savedSubtitle } from '../../lib/saved';
import { useStore } from '../../lib/store';
import { useImageScan } from '../../lib/useImageScan';
import { artboard, colors, DESKTOP_MIN, fonts, iconStroke, onColor } from '../../theme';

const WEEKDAYS = ['Chủ Nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy'];
const todayLabel = () => {
  const d = new Date();
  return `${WEEKDAYS[d.getDay()]}, ${d.getDate()} tháng ${d.getMonth() + 1}`;
};

export default function Home() {
  const desktop = useWindowDimensions().width >= DESKTOP_MIN;
  return desktop ? <HomeDesktop /> : <HomeMobile />;
}

function useHomeData() {
  const store = useStore();
  return { store, inFridge: store.pantry.filter((p) => p.checked) };
}

const openRecipe = (id: string) => router.push({ pathname: '/recipe/[id]', params: { id } });

// Lệch artboard có chủ đích (thay thẻ "Gợi ý nhanh" mock): 1–3 món mới lưu nhất từ GET /saved, không gọi /recipes/suggest.
function RecentSaved() {
  const { syncSaved, recentSaved } = useStore();
  useFocusEffect(
    useCallback(() => {
      void syncSaved(); // có thể vừa lưu / bỏ lưu ở màn khác
    }, [syncSaved]),
  );
  const { status, items, error } = recentSaved;

  if (error) {
    return (
      <View style={{ gap: 8 }}>
        <Txt v="caption" style={{ color: colors.danger }}>{error}</Txt>
        <Button kind="secondary" size="md" label="Thử lại" onPress={() => void syncSaved()} />
      </View>
    );
  }
  if (!items.length && status !== 'ready') return <Txt v="caption">Đang tải món đã lưu…</Txt>;
  if (!items.length) {
    return (
      <View style={st.empty}>
        <View style={[ui.thumb, { width: 56, height: 56, borderRadius: 18 }]}>
          <Bookmark size={24} color={colors.muted} strokeWidth={iconStroke} />
        </View>
        <Txt v="item">Chưa lưu món nào</Txt>
        <Txt v="caption" style={{ textAlign: 'center' }}>Chụp nguyên liệu để tìm món, rồi bấm lưu để xem lại ở đây.</Txt>
        <Button kind="secondary" size="md" icon={Camera} label="Chụp nguyên liệu" onPress={() => router.push('/camera')} />
      </View>
    );
  }
  return (
    <View style={{ gap: 10 }}>
      {items.map((item) => (
        <RecipeRow key={item.savedId} r={item.recipe} sub={savedSubtitle(item)} onPress={() => openRecipe(item.recipe.id)} />
      ))}
    </View>
  );
}

const recentTitle = 'Món đã lưu gần đây';
const seeAllSaved = <LinkText label="Xem tất cả" onPress={() => router.navigate('/saved')} />;

function HomeMobile() {
  const { inFridge } = useHomeData();
  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={[ui.scroll, { paddingTop: 28 }]} showsVerticalScrollIndicator={false}>
        <View style={[ui.row, { justifyContent: 'space-between', gap: 12 }]}>
          <View style={{ gap: 2, flexShrink: 1 }}>
            <Text style={st.date}>{todayLabel()}</Text>
            <Txt v="title">Tối nay nấu gì?</Txt>
          </View>
          <AccountButton />
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
          <FridgeChips items={inFridge} />
        </Section>

        <LogCard />

        <Section title={recentTitle} right={seeAllSaved}>
          <RecentSaved />
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}


function HomeDesktop() {
  const { store, inFridge } = useHomeData();
  const detected = store.scan?.items ?? [];
  const scan = useImageScan('push');

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingVertical: 30, paddingHorizontal: 34, gap: 22 }}>
      <View style={[ui.row, { justifyContent: 'space-between', alignItems: 'flex-end' }]}>
        <View style={{ gap: 5 }}>
          <Text style={st.date}>{todayLabel()}</Text>
          <Txt v="title" style={{ fontSize: 30, lineHeight: 36 }}>Tối nay nấu gì?</Txt>
        </View>
        <View style={[ui.row, { gap: 10 }]}>
          {store.userDataStatus === 'ready' && (
            <Text style={[st.date, { fontFamily: fonts.semibold }]}>
              {formatNum(store.log.kcal)}{store.kcalGoal ? ` / ${formatNum(store.kcalGoal)}` : ''} kcal hôm nay
            </Text>
          )}
          <AccountButton />
        </View>
      </View>

      <View style={{ flex: 1, flexDirection: 'row', gap: 24 }}>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ gap: 16 }} showsVerticalScrollIndicator={false}>
          <Pressable accessibilityRole="button" onPress={scan.scanFromLibrary} disabled={scan.busy} style={({ hovered }: PressState) => [st.drop, hovered && { borderColor: colors.primary }]}>
            <View style={st.dropIcon}>
              <ImagePlus size={26} color={colors.primary} strokeWidth={iconStroke} />
            </View>
            <Txt v="item" style={{ fontSize: 16 }}>Chọn ảnh nguyên liệu</Txt>
            <Txt v="caption" style={[{ fontSize: 13 }, scan.error && !scan.busy ? { color: colors.warn } : null]}>
              {scan.busy ? 'Đang nhận diện nguyên liệu…' : (scan.error ?? 'bấm để chọn ảnh · hoặc dùng webcam ở mục Chụp nguyên liệu')}
            </Txt>
          </Pressable>

          <Card style={{ gap: 14, padding: 18 }}>
            <Txt v="bodyStrong">
              {detected.length ? `AI nhận ra ${detected.length} nguyên liệu` : `Tủ lạnh có ${inFridge.length} nguyên liệu`}
            </Txt>
            {detected.length ? (
              <View style={ui.wrap}>
                {detected.map((d) => (
                  <Chip key={d.ingredientId} label={d.name} tone={d.sure ? 'safe' : 'warn'} />
                ))}
              </View>
            ) : (
              <FridgeChips items={inFridge} />
            )}
            <View style={{ height: 1, backgroundColor: colors.borderSoft }} />
            <View style={[ui.wrap, { alignItems: 'center' }]}>
              <Text style={[st.date, { fontFamily: fonts.bold }]}>Bộ lọc:</Text>
              <Chip small tone="safe" label={dietLabel(store.diet)} />
              {avoidLabels(store.avoid).map((label) => (
                <Chip key={label} small tone="danger" label={`Tránh ${label.toLowerCase()}`} />
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
          <Card style={{ padding: 22, borderRadius: 22 }}>
            <Section title={recentTitle} right={seeAllSaved}>
              <RecentSaved />
            </Section>
          </Card>
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
  empty: { alignItems: 'center', gap: 10, paddingVertical: 20, paddingHorizontal: 12 },
});
