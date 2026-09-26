import { router, Tabs } from 'expo-router';
import type { ComponentProps } from 'react';
import type { LucideIcon } from 'lucide-react-native';
import { Bookmark, Camera, ChefHat, Clock, Refrigerator } from 'lucide-react-native';
import { Pressable, PressableStateCallbackType, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { artboard, colors, fonts, iconStroke, onColor } from '../theme';
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
        <View style={st.brand}>
          <View style={st.logo}>
            <ChefHat size={20} color={onColor} strokeWidth={iconStroke} />
          </View>
          <Text style={st.brandText}>Bếp AI</Text>
        </View>
        <View style={{ gap: 4 }}>
          {ITEMS.map((i) => {
            const active = i.route === current;
            return (
              <Pressable
                key={i.key}
                accessibilityRole="tab"
                accessibilityState={{ selected: active }}
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
          <Text style={st.installTitle}>Cài Bếp AI vào máy</Text>
          <Text style={st.installText}>Cùng một bản web, cài từ trình duyệt là chạy như app.</Text>
          <Button size="md" label="Cài đặt" onPress={() => alertInstall()} />
        </View>
      </View>
    );
  }

  return (
    <View style={[st.bar, { height: 84 + Math.max(insets.bottom - 14, 0), paddingBottom: 14 + Math.max(insets.bottom - 14, 0) }]}>
      {ITEMS.map((i) => {
        const active = i.route === current;
        const c = active ? colors.primary : colors.muted;
        return (
          <Pressable
            key={i.key}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            accessibilityLabel={i.label}
            onPress={() => go(i)}
            style={({ pressed }) => [st.tab, pressed && { opacity: 0.6 }]}
          >
            <i.icon size={24} color={c} strokeWidth={iconStroke} />
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
    borderTopColor: colors.border,
    paddingHorizontal: 8,
  },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 5, paddingTop: 12, minHeight: 44 },
  tabLabel: { fontFamily: fonts.semibold, fontSize: 11 },
  side: {
    width: 236,
    paddingVertical: 28,
    paddingHorizontal: 18,
    borderRightWidth: 1,
    borderRightColor: colors.border,
    backgroundColor: colors.surface,
    gap: 26,
  },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 8 },
  logo: { width: 34, height: 34, borderRadius: 11, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  brandText: { fontFamily: fonts.display, fontSize: 19, color: colors.ink },
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
