import * as Clipboard from 'expo-clipboard';
import { router, useLocalSearchParams } from 'expo-router';
import { Bookmark, BookmarkCheck, Check, ChevronLeft, Copy, EyeOff, Image as ImageIcon, Info, RotateCw } from 'lucide-react-native';
import { useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { AiDishImage } from '../../components/AiDishImage';
import { IngredientRow, MetaChips, NutritionCard, StepList } from '../../components/recipe';
import { Button, Card, IconButton, SafetyBadge, Screen, Section, s as ui, Txt } from '../../components/ui';
import { useAuth } from '../../lib/auth';
import { fetchDishImage } from '../../lib/dishImage';
import { avoidLabels, dietLabel as labelOfDiet, haveIngredient, Recipe, recipeToText } from '../../lib/recipes';
import { useStore } from '../../lib/store';
import { useSubmit } from '../../lib/useSubmit';
import { artboard, colors, fonts, iconStroke } from '../../theme';

const IMAGE_FAILED = 'Chưa tạo được ảnh minh hoạ, thử lại';

export default function RecipeScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const store = useStore();
  const { getAccessToken } = useAuth();
  const r = store.findRecipe(id);
  const [copied, setCopied] = useState(false);
  // Lỗi (429 hết lượt ảnh hôm nay, 503 dịch vụ ảnh lỗi, mất mạng) hiện ở thẻ "Tạo" — không có ảnh giả thay thế.
  const image = useSubmit(IMAGE_FAILED);
  // Gắn theo recipe id: bấm "Món khác" (đổi id) thì ảnh món cũ tự ẩn, response trễ của món cũ không ghi đè.
  const [img, setImg] = useState<{ recipeId: string; url: string | null } | null>(null);
  const imgShown = img?.recipeId === id;
  const scroll = useRef<ScrollView>(null);

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

  const generate = () =>
    image.run(async () => {
      const recipeId = r.id;
      setImg({ recipeId, url: null });
      scroll.current?.scrollTo({ y: 0, animated: true });
      try {
        const out = await fetchDishImage(recipeId, r.name, await getAccessToken());
        setImg((cur) => (cur?.recipeId === recipeId ? { recipeId, url: out.url } : cur));
      } catch (error) {
        setImg(null);
        throw error;
      }
    });

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
      {imgShown && (
        <>
          <Card style={{ padding: 0, borderRadius: 22, overflow: 'hidden' }}>
            <AiDishImage url={img.url} name={r.name} />
            <View style={st.imgActions}>
              <Button kind="secondary" size="md" style={{ flex: 1 }} icon={RotateCw} label="Tạo lại" disabled={image.busy} onPress={generate} />
              <Button kind="secondary" size="md" style={{ flex: 1 }} icon={EyeOff} label="Ẩn ảnh" onPress={() => setImg(null)} />
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
      {[r.rawNote, r.warning].filter(Boolean).map((note) => (
        <SafetyBadge key={note} tone="warn" icon={Info}>
          {note}
        </SafetyBadge>
      ))}

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

      {/* Chỉ công thức thật (có recipe_id số) mới có ảnh AI; mock không gọi API. */}
      {!imgShown && r.source && (
        <Card dashed style={st.aiCard}>
          <View style={[ui.thumb, { width: 46, height: 46, borderRadius: 13 }]}>
            <ImageIcon size={22} color={colors.muted} strokeWidth={iconStroke} />
          </View>
          <View style={{ flex: 1, gap: 3 }}>
            <Txt v="bodyStrong">Xem ảnh món sau khi nấu</Txt>
            {image.error ? (
              <Text style={[st.aiSub, { color: colors.danger }]} accessibilityRole="alert">{image.error}</Text>
            ) : (
              <Text style={st.aiSub}>Ảnh do AI dựng, chỉ mang tính minh hoạ</Text>
            )}
          </View>
          <Button kind="outline" size="md" label={image.error ? 'Thử lại' : 'Tạo'} onPress={generate} />
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
