import { router, useLocalSearchParams } from 'expo-router';
import { ArrowLeft, ArrowRight, Check, X } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Button, Chip, IconButton, LinkText, SafetyBadge, Screen, Section, s as ui, Txt } from '../components/ui';
import { ALLERGENS, DIETS } from '../lib/recipes';
import { PantryItem, useStore } from '../lib/store';
import { artboard, colors, fonts, iconStroke, onColor } from '../theme';

export default function Confirm() {
  const { add } = useLocalSearchParams<{ add?: string }>();
  const store = useStore();
  const [adding, setAdding] = useState(add === '1');
  const [draft, setDraft] = useState('');
  const detectedCount = store.pantry.filter((p) => p.confidence !== undefined).length;
  const checked = store.pantry.filter((p) => p.checked).length;

  const submitDraft = () => {
    store.addItem(draft);
    setDraft('');
  };

  const find = () => {
    const ids = store.search();
    if (ids.length) router.push({ pathname: '/recipe/[id]', params: { id: ids[0] } });
  };
  const [tried, setTried] = useState(false);
  const noResult = tried && !store.results.length;

  return (
    <Screen
      header={
        <View style={st.header}>
          <IconButton icon={ArrowLeft} label="Quay lại" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
          <Txt v="title" style={{ fontSize: 22 }}>Kiểm tra trước khi nấu</Txt>
        </View>
      }
      footer={
        <View style={{ gap: 8 }}>
          {noResult && (
            <Text style={[st.hint, { color: colors.warn, textAlign: 'center' }]}>
              Không có món nào đạt bộ lọc — thử bỏ bớt dị ứng hoặc đổi chế độ ăn.
            </Text>
          )}
          <Button
            label="Tìm công thức"
            iconRight={ArrowRight}
            disabled={!checked}
            onPress={() => {
              setTried(true);
              find();
            }}
          />
        </View>
      }
    >
      <Section
        title={detectedCount ? `AI nhận ra ${detectedCount} nguyên liệu` : `Nguyên liệu đang có · ${store.pantry.length}`}
        right={<LinkText label={adding ? 'Xong' : '+ Thêm'} onPress={() => setAdding((a) => !a)} />}
      >
        <View style={{ gap: 8 }}>
          {adding && (
            <View style={st.addRow}>
              <TextInput
                autoFocus
                value={draft}
                onChangeText={setDraft}
                onSubmitEditing={submitDraft}
                placeholder="Tên nguyên liệu, vd: Đậu hũ"
                placeholderTextColor={colors.muted}
                returnKeyType="done"
                style={st.input}
                accessibilityLabel="Tên nguyên liệu mới"
              />
              <Button size="md" label="Thêm" disabled={!draft.trim()} onPress={submitDraft} />
            </View>
          )}
          {store.pantry.map((p) => (
            <IngredientCheck key={p.name} p={p} onToggle={() => store.toggleItem(p.name)} onRemove={() => store.removeItem(p.name)} />
          ))}
        </View>
      </Section>

      <Section title="Chế độ ăn">
        <View style={{ flexDirection: 'row', gap: 8 }} accessibilityRole="radiogroup">
          {DIETS.map((d) => {
            const on = store.diet === d.id;
            return (
              <Pressable
                key={d.id}
                accessibilityRole="radio"
                accessibilityState={{ checked: on }}
                onPress={() => store.setDiet(d.id)}
                style={({ pressed }) => [st.seg, on && st.segOn, pressed && { opacity: 0.85 }]}
              >
                <Text style={[st.segText, on && { color: onColor, fontFamily: fonts.bold }]}>{d.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </Section>

      <Section title="Tránh nguyên liệu gây dị ứng">
        <View style={ui.wrap}>
          {ALLERGENS.map((a) => {
            const on = store.avoid.includes(a.id);
            return (
              <Chip key={a.id} label={on ? `${a.label} ✕` : a.label} tone={on ? 'danger' : 'default'} selected={on} onPress={() => store.toggleAllergen(a.id)} />
            );
          })}
        </View>
      </Section>

      <SafetyBadge>
        Các lựa chọn này được áp thẳng vào bộ lọc công thức, không phải gợi ý mềm cho AI — món không phù hợp sẽ bị loại trước khi hiển thị.
      </SafetyBadge>
    </Screen>
  );
}

function IngredientCheck({ p, onToggle, onRemove }: { p: PantryItem; onToggle: () => void; onRemove: () => void }) {
  const unsure = p.confidence !== undefined && p.confidence < 80;
  return (
    <View style={[st.item, unsure && { borderStyle: 'dashed', borderColor: artboard.unsure }]}>
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: p.checked }}
        onPress={onToggle}
        style={({ pressed }) => [st.itemMain, pressed && { opacity: 0.7 }]}
      >
        <View style={[st.box, p.checked && st.boxOn]}>{p.checked && <Check size={14} color={onColor} strokeWidth={2.4} />}</View>
        <View style={{ flex: 1 }}>
          <Text style={st.itemName}>{p.name}</Text>
          {unsure && <Text style={[st.hint, { color: colors.warn }]}>Chưa chắc chắn — xác nhận giúp AI</Text>}
        </View>
        {p.confidence !== undefined && <Text style={[st.conf, unsure && { color: colors.warn }]}>{p.confidence}%</Text>}
      </Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel={`Xoá ${p.name}`} onPress={onRemove} hitSlop={6} style={({ pressed }) => [st.remove, pressed && { opacity: 0.6 }]}>
        <X size={16} color={colors.muted} strokeWidth={iconStroke} />
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 20, paddingTop: 24, paddingBottom: 12 },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 16,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    paddingRight: 4,
  },
  itemMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 13, paddingLeft: 14, minHeight: 50 },
  box: { width: 20, height: 20, borderRadius: 5, borderWidth: 1.5, borderColor: colors.muted, alignItems: 'center', justifyContent: 'center' },
  boxOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  itemName: { fontFamily: fonts.semibold, fontSize: 15, color: colors.ink },
  conf: { fontFamily: fonts.semibold, fontSize: 12, color: colors.primary },
  remove: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  hint: { fontFamily: fonts.medium, fontSize: 12 },
  seg: {
    flex: 1,
    minHeight: 44,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  segOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  segText: { fontFamily: fonts.semibold, fontSize: 14, color: colors.ink },
  addRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  input: {
    flex: 1,
    minHeight: 48,
    paddingHorizontal: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    fontFamily: fonts.medium,
    fontSize: 14,
    color: colors.ink,
  },
});
