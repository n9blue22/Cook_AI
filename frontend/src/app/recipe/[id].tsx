import * as Clipboard from 'expo-clipboard';
import { router, useLocalSearchParams } from 'expo-router';
import { Bookmark, BookmarkCheck, Check, ChevronLeft, Copy, EyeOff, Image as ImageIcon, RefreshCw } from 'lucide-react-native';
import { useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { AiDishImage } from '../../components/AiDishImage';
import { IngredientRow, MetaChips, NutritionCard, StepList } from '../../components/recipe';
import { Button, Card, IconButton, SafetyBadge, Screen, Section, s as ui, Txt } from '../../components/ui';
import { ALLERGENS, DIETS, getRecipe, haveIngredient, recipeToText } from '../../lib/recipes';
import { useStore } from '../../lib/store';
import { artboard, colors, fonts, iconStroke } from '../../theme';

type ImgState = 'idle' | 'loading' | 'shown';

export default function RecipeScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const store = useStore();
  const r = getRecipe(id);
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
  const pos = store.results.indexOf(r.id);
  const dietLabel = DIETS.find((d) => d.id === store.diet)!.label;
  const avoidLabel = store.avoid.map((a) => ALLERGENS.find((x) => x.id === a)!.label).join(', ');

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
    const nextId = store.results[(pos + 1) % store.results.length];
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
              <Button kind="secondary" size="md" style={{ flex: 1 }} icon={RefreshCw} label="Tạo lại" disabled={img === 'loading'} onPress={generate} />
              <Button kind="secondary" size="md" style={{ flex: 1 }} icon={EyeOff} label="Ẩn ảnh" onPress={() => setImg('idle')} />
            </View>
          </Card>
          <SafetyBadge tone="warn">
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

      <SafetyBadge title="Công thức lấy từ kho đã kiểm duyệt">
        Hợp chế độ: {dietLabel}
        {avoidLabel ? ` · Không chứa: ${avoidLabel}` : ''} · Đã kiểm tra nhiệt độ nấu chín
      </SafetyBadge>

      <NutritionCard r={r} />

      <Section title="Nguyên liệu">
        <View style={{ gap: 7 }}>
          {r.ingredients.map((i) => (
            <IngredientRow key={i.key} name={i.name} amount={i.amount} have={haveIngredient(pantry, i.key)} />
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

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 24, paddingBottom: 10 },
  imgActions: { flexDirection: 'row', gap: 10, padding: 14, paddingHorizontal: 16, borderTopWidth: 1, borderTopColor: colors.borderSoft },
  aiCard: { flexDirection: 'row', alignItems: 'center', gap: 13, borderRadius: 18, paddingVertical: 15, paddingHorizontal: 16, borderColor: artboard.dashed },
  aiSub: { fontFamily: fonts.medium, fontSize: 11.5, lineHeight: 17, color: colors.muted },
});
