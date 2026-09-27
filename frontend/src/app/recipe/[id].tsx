import * as Clipboard from 'expo-clipboard';
import { router, useLocalSearchParams } from 'expo-router';
import { Bookmark, BookmarkCheck, Check, ChevronLeft, Copy, EyeOff, Image as ImageIcon, Info, RotateCw } from 'lucide-react-native';
import { useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { AiDishImage } from '../../components/AiDishImage';
import { IngredientRow, MetaChips, NutritionCard, StepList } from '../../components/recipe';
import { Button, Card, IconButton, SafetyBadge, Screen, Section, s as ui, Txt } from '../../components/ui';
import { avoidLabels, dietLabel as labelOfDiet, haveIngredient, Recipe, recipeToText } from '../../lib/recipes';
import { useStore } from '../../lib/store';
import { artboard, colors, fonts, iconStroke } from '../../theme';

type ImgState = 'idle' | 'loading' | 'shown';

export default function RecipeScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const store = useStore();
  const r = store.findRecipe(id);
  const [copied, setCopied] = useState(false);
  const [img, setImg] = useState<ImgState>('idle');
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const scroll = useRef<ScrollView>(null);

  useEffect(() => {
    setImg('idle');
    return () => clearTimeout(timer.current);
  }, [id]);

  if (!r) {
    return (
      <Screen>
        <Txt v="title">Không tìm thấy công thức</Txt>
        <Button kind="secondary" label="Về trang chủ" onPress={() => router.replace('/')} />
      </Screen>
    );
  }

  const pantry = store.pantry.filter((p) => p.checked).map((p) => p.name);
  const saved = store.saved.some((x) => x.id === r.id);
  const pos = store.results.findIndex((x) => x.id === r.id);
  // Công thức thật đã lọc theo bộ lọc lúc tìm — user có thể đổi bộ lọc ở Confirm sau đó.
  const filters = pos >= 0 && store.searchedWith ? store.searchedWith : store;

  const copy = async () => {
    await Clipboard.setStringAsync(recipeToText(r));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  // ponytail: giả lập độ trễ gọi API tạo ảnh.
  const generate = () => {
    setImg('loading');
    scroll.current?.scrollTo({ y: 0, animated: true });
    timer.current = setTimeout(() => setImg('shown'), 1400);
  };

  const next = () => {
    const nextId = store.results[(pos + 1) % store.results.length].id;
    router.replace({ pathname: '/recipe/[id]', params: { id: nextId } });
  };

  return (
    <Screen
      scrollRef={scroll}
      header={
        <View style={st.header}>
          <IconButton icon={ChevronLeft} label="Quay lại" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
          <View style={[ui.row, { gap: 8 }]}>
            <IconButton icon={copied ? Check : Copy} label={copied ? 'Đã sao chép' : 'Sao chép công thức'} onPress={copy} />
            <IconButton filled icon={saved ? BookmarkCheck : Bookmark} label={saved ? 'Bỏ lưu công thức' : 'Lưu công thức'} onPress={() => store.toggleSaved(r.id)} />
          </View>
        </View>
      }
      footer={
        <View style={[ui.row, { gap: 10 }]}>
          {store.results.length > 1 && pos >= 0 && <Button kind="secondary" label="Món khác" onPress={next} />}
          <Button
            style={{ flex: 1 }}
            label={store.cooking?.id === r.id ? 'Tiếp tục nấu' : 'Bắt đầu nấu'}
            onPress={() => {
              store.startCooking(r.id);
              router.push('/cook');
            }}
          />
        </View>
      }
    >
      {img !== 'idle' && (
        <>
          <Card style={{ padding: 0, borderRadius: 22, overflow: 'hidden' }}>
            <AiDishImage loading={img === 'loading'} name={r.name} />
            <View style={st.imgActions}>
              <Button kind="secondary" size="md" style={{ flex: 1 }} icon={RotateCw} label="Tạo lại" disabled={img === 'loading'} onPress={generate} />
              <Button kind="secondary" size="md" style={{ flex: 1 }} icon={EyeOff} label="Ẩn ảnh" onPress={() => setImg('idle')} />
            </View>
          </Card>
          <SafetyBadge tone="warn" icon={Info}>
            Ảnh chỉ mô phỏng thành phẩm, không phải ảnh chụp món thật. Nguyên liệu và dinh dưỡng bên dưới mới là phần lấy từ kho đã kiểm duyệt.
          </SafetyBadge>
        </>
      )}

      <View style={{ gap: 10 }}>
        {pos >= 0 && (
          <Txt v="overline" style={{ color: colors.primary }}>
            Gợi ý {pos + 1} / {store.results.length}
          </Txt>
        )}
        <Txt v="title" style={{ fontSize: 32, lineHeight: 36 }}>{r.name}</Txt>
        <MetaChips r={r} />
      </View>

      <SafetyBadge title={SOURCE_TITLE[r.source ?? 'mock']}>{safetyText(r, labelOfDiet(filters.diet), avoidLabels(filters.avoid))}</SafetyBadge>
      {!!r.warning && (
        <SafetyBadge tone="warn" icon={Info}>
          {r.warning}
        </SafetyBadge>
      )}

      <NutritionCard r={r} />

      <Section title="Nguyên liệu">
        <View style={{ gap: 7 }}>
          {r.ingredients.map((i) => (
            <IngredientRow key={i.key} name={i.name} amount={i.amount} have={i.have ?? haveIngredient(pantry, i.key)} />
          ))}
        </View>
      </Section>

      <Section title="Cách nấu">
        <StepList steps={r.steps} />
      </Section>

      {img === 'idle' && (
        <Card dashed style={st.aiCard}>
          <View style={[ui.thumb, { width: 46, height: 46, borderRadius: 13 }]}>
            <ImageIcon size={22} color={colors.muted} strokeWidth={iconStroke} />
          </View>
          <View style={{ flex: 1, gap: 3 }}>
            <Txt v="bodyStrong">Xem ảnh món sau khi nấu</Txt>
            <Text style={st.aiSub}>Ảnh do AI dựng, chỉ mang tính minh hoạ</Text>
          </View>
          <Button kind="outline" size="md" label="Tạo" onPress={generate} />
        </Card>
      )}
    </Screen>
  );
}

const SOURCE_TITLE = {
  adapted: 'AI chỉnh theo nguyên liệu bạn có',
  original: 'Công thức gốc từ kho đã kiểm duyệt',
  mock: 'Công thức lấy từ kho đã kiểm duyệt',
} as const;
const SECONDS_PER_MINUTE = 60;

const restLabel = (sec: number) =>
  sec >= SECONDS_PER_MINUTE ? `${Math.round(sec / SECONDS_PER_MINUTE)} phút` : `${sec} giây`;

// Chỉ bản AI chỉnh mới qua lớp kiểm tra nhiệt độ ở backend; bản gốc là fallback khi AI lỗi hoặc không qua kiểm tra.
function safetyText(r: Recipe, diet: string, avoid: string[]): string {
  return [
    r.source === 'adapted' ? 'Lấy từ kho đã kiểm duyệt, AI chỉnh lượng/bước theo đồ bạn có' : null,
    r.source === 'original' ? 'AI chưa chỉnh được món này nên giữ nguyên bản gốc' : null,
    `Hợp chế độ: ${diet}`,
    avoid.length ? `Không chứa: ${avoid.join(', ')}` : null,
    r.source === 'original' ? null : 'Đã kiểm tra nhiệt độ nấu chín',
    r.restSec ? `Để nghỉ ${restLabel(r.restSec)} sau khi tắt bếp rồi mới ăn` : null,
  ].filter(Boolean).join(' · ');
}

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 24, paddingBottom: 10 },
  imgActions: { flexDirection: 'row', gap: 10, padding: 14, paddingHorizontal: 16, borderTopWidth: 1, borderTopColor: colors.borderSoft },
  aiCard: { flexDirection: 'row', alignItems: 'center', gap: 13, borderRadius: 18, paddingVertical: 15, paddingHorizontal: 16, borderColor: artboard.dashed },
  aiSub: { fontFamily: fonts.medium, fontSize: 11.5, lineHeight: 17, color: colors.muted },
});
