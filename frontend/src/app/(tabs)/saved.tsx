import * as Clipboard from 'expo-clipboard';
import { router, useFocusEffect } from 'expo-router';
import { Bookmark, Check, ChevronRight, Copy, Search, Trash, Utensils } from 'lucide-react-native';
import { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Button, SafetyBadge, Screen, s as ui, Txt } from '../../components/ui';
import { Recipe, recipeToText } from '../../lib/recipes';
import { matchesFilter, SavedFilter, SavedRecipe } from '../../lib/saved';
import { useStore } from '../../lib/store';
import { artboard, colors, fonts, iconStroke, onColor } from '../../theme';

const SEARCH_DEBOUNCE_MS = 300;
const NONE_OPEN = -1; // savedId thật luôn > 0

const ago = (t: number) => {
  const days = Math.floor((Date.now() - t) / 86_400_000);
  return days <= 0 ? 'lưu hôm nay' : `lưu ${days} ngày trước`;
};

export default function Saved() {
  const store = useStore();
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState<SavedFilter>('all');
  // null = chưa bấm món nào → món mới lưu gần nhất mở sẵn các nút Mở / Sao chép / Xoá (Saved.dc.html).
  const [open, setOpen] = useState<number | null>(null);
  const { loadSaved, removeSaved, savedList } = store;

  // Tải lại mỗi lần vào tab (có thể vừa lưu món ở màn khác) và khi gõ tìm (server lọc theo tên, chờ gõ xong).
  useFocusEffect(
    useCallback(() => {
      const timer = setTimeout(() => void loadSaved(q), SEARCH_DEBOUNCE_MS);
      return () => clearTimeout(timer);
    }, [loadSaved, q]),
  );

  const all = savedList.items;
  const list = all.filter((item) => matchesFilter(item, filter));
  const openId = open ?? all[0]?.savedId ?? null;
  const searching = q.trim() !== '';

  const filters: { id: SavedFilter; label: string }[] = [
    { id: 'all', label: `Tất cả · ${all.length}` },
    { id: 'quick', label: 'Nhanh dưới 20′' },
    { id: 'veg', label: 'Chay' },
  ];

  return (
    <Screen contentStyle={{ paddingTop: 28, gap: 16 }}>
      <Txt v="title">Công thức đã lưu</Txt>

      <View style={st.search}>
        <Search size={18} color={colors.muted} strokeWidth={iconStroke} />
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="Tìm theo tên món"
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
              role="radio"
              aria-checked={on}
              onPress={() => setFilter(f.id)}
              style={({ pressed }) => [st.filter, on && st.filterOn, pressed && { opacity: 0.8 }]}
            >
              <Text style={[st.filterText, on && { color: onColor, fontFamily: fonts.bold }]}>{f.label}</Text>
            </Pressable>
          );
        })}
      </View>

      {savedList.error && (
        <View style={{ gap: 8 }}>
          <Txt v="caption" style={{ color: colors.danger }}>{savedList.error}</Txt>
          <Button kind="secondary" size="md" label="Thử lại" onPress={() => void loadSaved(q)} />
        </View>
      )}

      {savedList.status !== 'ready' && all.length === 0 ? (
        savedList.status === 'loading' && <Txt v="caption" style={{ textAlign: 'center', paddingVertical: 20 }}>Đang tải…</Txt>
      ) : all.length === 0 && !searching ? (
        <View style={st.empty}>
          <View style={[ui.thumb, { width: 64, height: 64, borderRadius: 20 }]}>
            <Bookmark size={28} color={colors.muted} strokeWidth={iconStroke} />
          </View>
          <Txt v="item">Chưa lưu công thức nào</Txt>
          <Txt v="caption" style={{ textAlign: 'center' }}>Bấm biểu tượng lưu ở trang công thức để xem lại sau.</Txt>
          <Button kind="secondary" size="md" label="Tìm món" onPress={() => router.navigate('/')} />
        </View>
      ) : list.length === 0 ? (
        <Txt v="caption" style={{ textAlign: 'center', paddingVertical: 20 }}>Không có món nào khớp.</Txt>
      ) : (
        <View style={{ gap: 10 }}>
          {list.map((item) => (
            <SavedItem
              key={item.savedId}
              r={item.recipe}
              sub={subtitle(item)}
              open={openId === item.savedId}
              onToggle={() => setOpen(openId === item.savedId ? NONE_OPEN : item.savedId)}
              onDelete={() => void removeSaved(item.savedId)}
            />
          ))}
        </View>
      )}

      {/* Chưa có cache offline (TODO PWA, feature-spec §7 bước 11) — không hứa "xem được khi mất mạng". */}
      <SafetyBadge icon={Bookmark}>Công thức đã lưu nằm trong tài khoản của bạn — đăng nhập ở máy khác vẫn thấy, cần có mạng để tải.</SafetyBadge>
    </Screen>
  );
}

// Thiếu thời gian / dinh dưỡng thì bỏ phần đó, không đoán số.
function subtitle({ recipe: r, diet, savedAt }: SavedRecipe): string {
  const vegetarian = diet === 'vegetarian' || diet === 'vegan';
  return [r.minutes && `${r.minutes} phút`, r.nutrition && `${r.nutrition.kcal} kcal`, vegetarian ? 'chay' : ago(savedAt)]
    .filter(Boolean)
    .join(' · ');
}

function SavedItem({ r, sub, open, onToggle, onDelete }: { r: Recipe; sub: string; open: boolean; onToggle: () => void; onDelete: () => void }) {
  const [copied, setCopied] = useState(false);
  const [confirmDel, setConfirmDel] = useState(false);

  const copy = async () => {
    await Clipboard.setStringAsync(recipeToText(r));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <View style={st.item}>
      <Pressable
        role="button"
        aria-expanded={open}
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
        {/* Đang mở thì không có mũi tên (artboard); trạng thái mở báo qua aria-expanded */}
        {!open && <ChevronRight size={18} color={colors.muted} strokeWidth={iconStroke} />}
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
              <Trash size={17} color={colors.danger} strokeWidth={iconStroke} />
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
