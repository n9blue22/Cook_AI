import { router, useLocalSearchParams } from 'expo-router';
import { ArrowRight, Check, ChevronLeft, X } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Button, Chip, IconButton, LinkText, SafetyBadge, Screen, Section, s as ui, Txt } from '../components/ui';
import { ALLERGENS, DIETS } from '../lib/recipes';
import { MIN_CONFIDENT_PCT, useStore } from '../lib/store';
import { artboard, colors, fonts, iconStroke, onColor } from '../theme';

type Row = { name: string; checked: boolean; confidence?: number };

type RowsModel = {
  rows: Row[];
  toggle: (name: string) => void;
  remove?: (name: string) => void; // không có = không hiện nút xoá
  add: (name: string) => void;
  find: () => string[]; // id công thức tìm được
};

// Vừa quét ảnh (Confirm.dc.html): tick chỉ là lựa chọn cho lần tìm này. Bấm tìm → món đã tick được BỔ SUNG
// vào tủ; món có sẵn trong tủ không bao giờ bị bỏ/ẩn chỉ vì lần quét này không thấy rõ.
function useScanRows(): RowsModel {
  const store = useStore();
  const [picked, setPicked] = useState(() =>
    store.lastScan.filter((d) => d.confidence >= MIN_CONFIDENT_PCT).map((d) => d.name),
  );
  const [addedHere, setAddedHere] = useState<string[]>([]);
  const rows: Row[] = [
    ...store.lastScan.map((d) => ({ ...d, checked: picked.includes(d.name) })),
    ...addedHere.map((name) => ({ name, checked: picked.includes(name) })),
  ];
  const pick = (name: string) => setPicked((names) => (names.includes(name) ? names : [...names, name]));
  return {
    rows,
    toggle: (name) => setPicked((names) => (names.includes(name) ? names.filter((n) => n !== name) : [...names, name])),
    add(name) {
      if (!rows.some((r) => r.name.toLowerCase() === name.toLowerCase())) setAddedHere((names) => [...names, name]);
      pick(rows.find((r) => r.name.toLowerCase() === name.toLowerCase())?.name ?? name);
    },
    find() {
      store.addConfirmed(picked);
      return store.search(picked);
    },
  };
}

// Sửa tủ lạnh từ Main: thao tác thẳng trên tủ, có nút xoá.
function usePantryRows(): RowsModel {
  const store = useStore();
  return { rows: store.pantry, toggle: store.toggleItem, remove: store.removeItem, add: store.addItem, find: () => store.search() };
}

// scan=1: màn sau khi quét ảnh. Không có scan: sửa tủ lạnh từ Main.
export default function Confirm() {
  const { add, scan } = useLocalSearchParams<{ add?: string; scan?: string }>();
  const scanned = scan === '1';
  const store = useStore();
  const scanRows = useScanRows();
  const pantryRows = usePantryRows();
  const model = scanned ? scanRows : pantryRows;
  const [adding, setAdding] = useState(add === '1');
  const [draft, setDraft] = useState('');
  const detectedCount = model.rows.filter((r) => r.confidence !== undefined).length;
  const hasChecked = model.rows.some((r) => r.checked);

  const submitDraft = () => {
    const name = draft.trim();
    if (!name) return;
    model.add(name);
    setDraft('');
  };

  const find = () => {
    const ids = model.find();
    if (ids.length) router.push({ pathname: '/recipe/[id]', params: { id: ids[0] } });
  };
  const [tried, setTried] = useState(false);
  const noResult = tried && !store.results.length;

  return (
    <Screen
      header={
        <View style={st.header}>
          <IconButton icon={ChevronLeft} label="Quay lại" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
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
            disabled={!hasChecked}
            onPress={() => {
              setTried(true);
              find();
            }}
          />
        </View>
      }
    >
      <Section
        titleV="bodyStrong"
        title={scanned ? `AI nhận ra ${detectedCount} nguyên liệu` : `Nguyên liệu đang có · ${model.rows.length}`}
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
          {model.rows.map((r) => (
            <IngredientCheck
              key={r.name}
              p={r}
              onToggle={() => model.toggle(r.name)}
              onRemove={model.remove && (() => model.remove?.(r.name))}
            />
          ))}
        </View>
      </Section>

      <Section titleV="bodyStrong" title="Chế độ ăn">
        <View style={{ flexDirection: 'row', gap: 8 }} accessibilityRole="radiogroup">
          {DIETS.map((d) => {
            const on = store.diet === d.id;
            return (
              <Pressable
                key={d.id}
                role="radio"
                aria-checked={on}
                onPress={() => store.setDiet(d.id)}
                style={({ pressed }) => [st.seg, on && st.segOn, pressed && { opacity: 0.85 }]}
              >
                <Text style={[st.segText, on && { color: onColor, fontFamily: fonts.bold }]}>{d.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </Section>

      <Section titleV="bodyStrong" title="Tránh nguyên liệu gây dị ứng">
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

// onRemove không truyền = không có nút xoá (màn vừa quét, như artboard).
function IngredientCheck({ p, onToggle, onRemove }: { p: Row; onToggle: () => void; onRemove?: () => void }) {
  const unsure = p.confidence !== undefined && p.confidence < MIN_CONFIDENT_PCT;
  return (
    <View style={[st.item, !onRemove && { paddingRight: 14 }, unsure && { borderStyle: 'dashed', borderColor: artboard.unsure }]}>
      <Pressable
        role="checkbox"
        aria-checked={p.checked}
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
      {onRemove && (
        <Pressable accessibilityRole="button" accessibilityLabel={`Xoá ${p.name}`} onPress={onRemove} hitSlop={6} style={({ pressed }) => [st.remove, pressed && { opacity: 0.6 }]}>
          <X size={16} color={colors.muted} strokeWidth={iconStroke} />
        </Pressable>
      )}
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
  itemMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, paddingLeft: 14, minHeight: 52 },
  box: { width: 20, height: 20, borderRadius: 5, borderWidth: 1.5, borderColor: colors.muted, alignItems: 'center', justifyContent: 'center' },
  boxOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  itemName: { fontFamily: fonts.semibold, fontSize: 15, color: colors.ink },
  conf: { fontFamily: fonts.semibold, fontSize: 12, color: colors.primary },
  remove: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  hint: { fontFamily: fonts.medium, fontSize: 12 },
  seg: {
    flexGrow: 1, // như artboard: rộng theo chữ + chia phần dư (không chia đều)
    paddingHorizontal: 6,
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
