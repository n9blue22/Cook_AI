import { router, Tabs } from 'expo-router';
import type { ComponentProps } from 'react';
import type { LucideIcon } from 'lucide-react-native';
import { Bookmark, Camera, Clock, Refrigerator } from 'lucide-react-native';
import { Pressable, PressableStateCallbackType, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { artboard, colors, fonts, iconStroke } from '../theme';
import { BrandMark } from './BrandMark';
import { Button } from './ui';

type TabBarRenderProps = Parameters<NonNullable<ComponentProps<typeof Tabs>['tabBar']>>[0];
// react-native-web có thêm hovered.
export type PressState = PressableStateCallbackType & { hovered?: boolean };

// "Chụp" và "Đang nấu" là màn toàn màn hình (không có tab bar) nên mở bằng push.
const ITEMS: { key: string; label: string; long: string; icon: LucideIcon; route?: string; href?: '/camera' | '/cook' }[] = [
  { key: 'index', label: 'Tủ lạnh', long: 'Tủ lạnh', icon: Refrigerator, route: 'index' },
  { key: 'camera', label: 'Chụp', long: 'Chụp nguyên liệu', icon: Camera, href: '/camera' },
  { key: 'saved', label: 'Đã lưu', long: 'Đã lưu', icon: Bookmark, route: 'saved' },
  { key: 'cook', label: 'Đang nấu', long: 'Đang nấu', icon: Clock, href: '/cook' },
];

export function BottomTabBar({ state, navigation, desktop }: TabBarRenderProps & { desktop: boolean }) {
  const insets = useSafeAreaInsets();
  const current = state.routes[state.index]?.name;
  const go = (i: (typeof ITEMS)[number]) => (i.href ? router.push(i.href) : navigation.navigate(i.route!));

  if (desktop) {
    return (
      <View style={st.side}>
        <BrandMark style={{ paddingHorizontal: 8 }} />
        <View style={{ gap: 4 }}>
          {ITEMS.map((i) => {
            const active = i.route === current;
            return (
              <Pressable
                key={i.key}
                role="tab"
                aria-selected={active}
                onPress={() => go(i)}
                style={({ hovered, pressed }: PressState) => [
                  st.sideItem,
                  (hovered || pressed) && { backgroundColor: colors.bg },
                  active && { backgroundColor: colors.primarySoft },
                ]}
              >
                <i.icon size={20} color={active ? colors.primary : artboard.sidebarInk} strokeWidth={iconStroke} />
                <Text style={[st.sideLabel, active && { color: colors.primary, fontFamily: fonts.bold }]}>{i.long}</Text>
              </Pressable>
            );
          })}
        </View>
        <View style={{ flex: 1 }} />
        <View style={st.install}>
          <Text style={st.installTitle}>Cài Chef AI vào máy</Text>
          <Text style={st.installText}>Cùng một bản web, cài từ trình duyệt là chạy như app.</Text>
          <Button size="md" label="Cài đặt" onPress={() => alertInstall()} />
        </View>
      </View>
    );
  }

  return (
    <View style={[st.bar, { height: 82 + Math.max(insets.bottom - 12, 0), paddingBottom: 10 + Math.max(insets.bottom - 12, 0) }]}>
      {ITEMS.map((i) => {
        const active = i.route === current;
        const c = active ? colors.primary : colors.muted;
        return (
          <Pressable
            key={i.key}
            role="tab"
            aria-selected={active}
            accessibilityLabel={i.label}
            onPress={() => go(i)}
            style={({ pressed }) => [st.tab, pressed && { opacity: 0.7 }]}
          >
            <View style={[st.iconWrap, active && st.iconWrapActive]}>
              <i.icon size={22} color={c} strokeWidth={active ? 2.2 : iconStroke} />
            </View>
            <Text style={[st.tabLabel, { color: c }, active && { fontFamily: fonts.bold }]}>{i.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// ponytail: chỉ hướng dẫn cài thủ công; nối beforeinstallprompt khi có service worker PWA.
function alertInstall() {
  if (typeof window !== 'undefined' && window.alert) {
    window.alert('Mở menu trình duyệt → "Cài đặt ứng dụng" / "Thêm vào màn hình chính".');
  }
}

const st = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.borderSoft,
    paddingHorizontal: 8,
    boxShadow: '0 -3px 10px rgba(0, 0, 0, 0.03)',
    elevation: 8,
  },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 3, paddingTop: 6, minHeight: 48 },
  iconWrap: { width: 44, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  iconWrapActive: { backgroundColor: colors.primarySoft },
  tabLabel: { fontFamily: fonts.semibold, fontSize: 11, letterSpacing: -0.1 },
  side: {
    width: 236,
    paddingVertical: 28,
    paddingHorizontal: 18,
    borderRightWidth: 1,
    borderRightColor: colors.border,
    backgroundColor: colors.surface,
    gap: 26,
  },
  sideItem: { flexDirection: 'row', alignItems: 'center', gap: 11, minHeight: 46, paddingHorizontal: 14, borderRadius: 14 },
  sideLabel: { fontFamily: fonts.semibold, fontSize: 14, color: artboard.sidebarInk },
  install: {
    padding: 15,
    borderRadius: 16,
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: colors.primaryLine,
    gap: 10,
  },
  installTitle: { fontFamily: fonts.bold, fontSize: 13, color: artboard.onPrimarySoft },
  installText: { fontFamily: fonts.medium, fontSize: 11.5, lineHeight: 17, color: artboard.onPrimarySoftMuted },
});
