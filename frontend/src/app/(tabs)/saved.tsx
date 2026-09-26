import * as Clipboard from 'expo-clipboard';
import { router } from 'expo-router';
import { Bookmark, Check, ChevronDown, ChevronRight, Copy, Search, Trash, Utensils } from 'lucide-react-native';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Button, SafetyBadge, Screen, s as ui, Txt } from '../../components/ui';
import { getRecipe, Recipe, recipeToText } from '../../lib/recipes';
import { useStore } from '../../lib/store';
import { artboard, colors, fonts, iconStroke, onColor } from '../../theme';

type Filter = 'all' | 'quick' | 'veg';

const ago = (t: number) => {
  const days = Math.floor((Date.now() - t) / 86_400_000);
  return days <= 0 ? 'lưu hôm nay' : `lưu ${days} ngày trước`;
};

export default function Saved() {
  const store = useStore();
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [open, setOpen] = useState<string | null>(null);

  const all = useMemo(
    () => store.saved.map((x) => ({ r: getRecipe(x.id), at: x.savedAt })).filter((x): x is { r: Recipe; at: number } => !!x.r),
    [store.saved],
  );
  const needle = q.trim().toLowerCase();
  const list = all.filter(
    ({ r }) =>
      (filter === 'all' || (filter === 'quick' ? r.minutes < 20 : r.diet !== 'man')) &&
      (!needle || r.name.toLowerCase().includes(needle) || r.ingredients.some((i) => i.name.toLowerCase().includes(needle))),
  );

  const filters: { id: Filter; label: string }[] = [
    { id: 'all', label: `Tất cả · ${all.length}` },
    { id: 'quick', label: 'Nhanh dưới 20′' },
    { id: 'veg', label: 'Chay' },
  ];

  return (
    <Screen>
      <View style={{ height: 22 }} />
      <Txt v="title">Công thức đã lưu</Txt>

      <View style={st.search}>
        <Search size={18} color={colors.muted} strokeWidth={iconStroke} />
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="Tìm món hoặc nguyên liệu"
          placeholderTextColor={colors.muted}
          accessibilityLabel="Tìm trong công thức đã lưu"
          style={st.input}
        />
      </View>

      <View style={[ui.row, { gap: 8, flexWrap: 'wrap' }]}>
        {filters.map((f) => {
          const on = f.id === filter;
          return (
            <Pressable
              key={f.id}
              accessibilityRole="button"
              accessibilityState={{ selected: on }}
              onPress={() => setFilter(f.id)}
              style={({ pressed }) => [st.filter, on && st.filterOn, pressed && { opacity: 0.8 }]}
            >
              <Text style={[st.filterText, on && { color: onColor, fontFamily: fonts.bold }]}>{f.label}</Text>
            </Pressable>
          );
        })}
      </View>

      {all.length === 0 ? (
        <View style={st.empty}>
          <View style={[ui.thumb, { width: 64, height: 64, borderRadius: 20 }]}>
            <Bookmark size={28} color={colors.muted} strokeWidth={iconStroke} />
          </View>
          <Txt v="item">Chưa lưu công thức nào</Txt>
          <Txt v="caption" style={{ textAlign: 'center' }}>Bấm biểu tượng lưu ở trang công thức để xem lại sau, kể cả khi mất mạng.</Txt>
          <Button kind="secondary" size="md" label="Tìm món" onPress={() => router.navigate('/')} />
        </View>
      ) : list.length === 0 ? (
        <Txt v="caption" style={{ textAlign: 'center', paddingVertical: 20 }}>Không có món nào khớp.</Txt>
      ) : (
        <View style={{ gap: 10 }}>
          {list.map(({ r, at }) => (
            <SavedItem
              key={r.id}
              r={r}
              sub={`${r.minutes} phút · ${r.kcal} kcal · ${r.diet === 'man' ? ago(at) : 'chay'}`}
              open={open === r.id}
              onToggle={() => setOpen(open === r.id ? null : r.id)}
              onDelete={() => store.toggleSaved(r.id)}
            />
          ))}
        </View>
      )}

      <SafetyBadge>Công thức đã lưu xem được cả khi mất mạng — app cài từ trình duyệt vẫn giữ nguyên dữ liệu.</SafetyBadge>
    </Screen>
  );
}

function SavedItem({ r, sub, open, onToggle, onDelete }: { r: Recipe; sub: string; open: boolean; onToggle: () => void; onDelete: () => void }) {
  const [copied, setCopied] = useState(false);
  const [confirmDel, setConfirmDel] = useState(false);
  const Chevron = open ? ChevronDown : ChevronRight;

  const copy = async () => {
    await Clipboard.setStringAsync(recipeToText(r));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <View style={st.item}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        onPress={onToggle}
        style={({ pressed }) => [ui.row, { gap: 13 }, pressed && { opacity: 0.8 }]}
      >
        <View style={[ui.thumb, { width: 52, height: 52 }]}>
          <Utensils size={22} color={colors.muted} strokeWidth={iconStroke} />
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          <Txt v="item">{r.name}</Txt>
          <Txt v="caption">{sub}</Txt>
        </View>
        <Chevron size={20} color={colors.muted} strokeWidth={iconStroke} />
      </Pressable>

      {open && (
        <View style={[ui.row, { gap: 8, marginTop: 12 }]}>
          <Button kind="soft" size="md" style={{ flex: 1 }} label="Mở" onPress={() => router.push({ pathname: '/recipe/[id]', params: { id: r.id } })} />
          <Button kind="secondary" size="md" icon={copied ? Check : Copy} label={copied ? 'Đã chép' : 'Sao chép'} onPress={copy} />
          {confirmDel ? (
            <Button
              kind="danger"
              size="md"
              label="Xoá?"
              onPress={onDelete}
              onBlur={() => setConfirmDel(false)}
              accessibilityLabel={`Xác nhận xoá ${r.name}`}
            />
          ) : (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Xoá công thức ${r.name}`}
              onPress={() => setConfirmDel(true)}
              style={({ pressed }) => [st.del, pressed && { opacity: 0.7 }]}
            >
              <Trash size={18} color={colors.danger} strokeWidth={iconStroke} />
            </Pressable>
          )}
        </View>
      )}
    </View>
  );
}

const st = StyleSheet.create({
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    minHeight: 48,
    paddingHorizontal: 14,
    borderRadius: 16,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  input: { flex: 1, minHeight: 46, fontFamily: fonts.medium, fontSize: 14, color: colors.ink },
  filter: {
    minHeight: 44,
    paddingHorizontal: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    justifyContent: 'center',
  },
  filterOn: { backgroundColor: colors.ink, borderColor: colors.ink },
  filterText: { fontFamily: fonts.semibold, fontSize: 13, color: colors.ink },
  item: { padding: 14, borderRadius: 18, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  del: {
    width: 44,
    minHeight: 44,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: artboard.dangerLine,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  empty: { alignItems: 'center', gap: 10, paddingVertical: 28, paddingHorizontal: 20 },
});
