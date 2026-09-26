import type { LucideIcon } from 'lucide-react-native';
import { ShieldCheck, TriangleAlert } from 'lucide-react-native';
import { ReactNode, Ref } from 'react';
import {
  Pressable,
  PressableProps,
  ScrollView,
  StyleProp,
  StyleSheet,
  Text,
  TextProps,
  TextStyle,
  View,
  ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { artboard, colors, fonts, iconStroke, onColor, radius, typography } from '../theme';

type TxtVariant = keyof typeof typography;

export function Txt({ v = 'body', style, ...p }: TextProps & { v?: TxtVariant; style?: StyleProp<TextStyle> }) {
  return <Text {...p} style={[typography[v], style]} />;
}

const pressed = (base: StyleProp<ViewStyle>) => ({ pressed }: { pressed: boolean }) => [
  base,
  pressed && { opacity: 0.82, transform: [{ scale: 0.985 }] },
];

type BtnProps = Omit<PressableProps, 'style' | 'children'> & {
  label: string;
  kind?: 'primary' | 'secondary' | 'outline' | 'soft' | 'danger';
  icon?: LucideIcon;
  iconRight?: LucideIcon;
  style?: StyleProp<ViewStyle>;
  size?: 'lg' | 'md';
};

export function Button({ label, kind = 'primary', icon: I, iconRight: IR, style, size = 'lg', disabled, ...p }: BtnProps) {
  const fg = kind === 'primary' || kind === 'danger' ? onColor : kind === 'secondary' ? colors.ink : colors.primary;
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      {...p}
      style={pressed([
        s.btn,
        size === 'md' && s.btnMd,
        kind === 'primary' && { backgroundColor: colors.primary },
        kind === 'secondary' && s.btnSecondary,
        kind === 'outline' && { borderWidth: 1, borderColor: colors.primary, backgroundColor: colors.surface },
        kind === 'soft' && { backgroundColor: colors.primarySoft },
        kind === 'danger' && { backgroundColor: colors.danger },
        disabled && { opacity: 0.45 },
        style,
      ])}
    >
      {I && <I size={18} color={fg} strokeWidth={iconStroke} />}
      <Text style={[s.btnLabel, size === 'md' && { fontSize: 13 }, { color: fg }]}>{label}</Text>
      {IR && <IR size={18} color={fg} strokeWidth={iconStroke} />}
    </Pressable>
  );
}

export function IconButton({
  icon: I,
  label,
  onPress,
  filled,
  dark,
  square,
}: {
  icon: LucideIcon;
  label: string;
  onPress?: () => void;
  filled?: boolean;
  dark?: boolean;
  square?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      hitSlop={4}
      style={pressed([
        s.iconBtn,
        square && { borderRadius: radius.chip },
        filled && { backgroundColor: colors.primary, borderColor: colors.primary },
        dark && { backgroundColor: artboard.cam.chip, borderColor: artboard.cam.chip },
      ])}
    >
      <I size={20} color={filled || dark ? onColor : colors.ink} strokeWidth={iconStroke} />
    </Pressable>
  );
}

export function Chip({
  label,
  tone = 'default',
  onPress,
  selected,
  small,
  medium,
}: {
  label: string;
  tone?: 'default' | 'warn' | 'alt' | 'safe' | 'danger' | 'dark';
  onPress?: () => void;
  selected?: boolean;
  small?: boolean;
  medium?: boolean; // chữ 500 thay vì 600 (chip tủ lạnh ở Main.dc.html)
}) {
  const t = chipTone[tone];
  const body = (
    <Text style={[s.chipText, small && { fontSize: 12 }, medium && { fontFamily: fonts.medium }, { color: t.fg }]} numberOfLines={1}>
      {label}
    </Text>
  );
  const style = [s.chip, small && s.chipSmall, { backgroundColor: t.bg, borderColor: t.line }];
  if (!onPress) return <View style={style}>{body}</View>;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={pressed([style, { minHeight: 44, justifyContent: 'center' }])}
    >
      {body}
    </Pressable>
  );
}

const chipTone = {
  default: { bg: colors.surface, line: colors.border, fg: colors.ink },
  warn: { bg: colors.warnBg, line: colors.warnLine, fg: colors.warn },
  alt: { bg: colors.surfaceAlt, line: colors.surfaceAlt, fg: colors.ink },
  safe: { bg: colors.primarySoft, line: colors.primaryLine, fg: artboard.onPrimarySoft },
  danger: { bg: colors.danger, line: colors.danger, fg: onColor },
  dark: { bg: colors.ink, line: colors.ink, fg: onColor },
};

export function Card({ children, style, dashed }: { children: ReactNode; style?: StyleProp<ViewStyle>; dashed?: boolean }) {
  return <View style={[s.card, dashed && { borderStyle: 'dashed', borderColor: artboard.dashed }, style]}>{children}</View>;
}

// Khối thông báo an toàn / cảnh báo (SafetyBadge trong spec).
export function SafetyBadge({ tone = 'safe', title, children }: { tone?: 'safe' | 'warn'; title?: string; children: ReactNode }) {
  const safe = tone === 'safe';
  const I = safe ? ShieldCheck : TriangleAlert;
  return (
    <View
      style={[
        s.notice,
        { backgroundColor: safe ? colors.primarySoft : colors.warnBg, borderColor: safe ? colors.primaryLine : colors.warnLine },
      ]}
    >
      <I size={18} color={safe ? colors.primary : colors.warn} strokeWidth={iconStroke} />
      <View style={{ flex: 1, gap: 2 }}>
        {title && <Text style={[s.noticeText, { fontFamily: fonts.semibold, color: artboard.onPrimarySoft }]}>{title}</Text>}
        <Text style={[s.noticeText, { color: safe ? (title ? artboard.onPrimarySoftMuted : artboard.onPrimarySoft) : artboard.onWarnBg }]}>
          {children}
        </Text>
      </View>
    </View>
  );
}

export function Section({ title, right, children, gap = 10 }: { title: string; right?: ReactNode; children: ReactNode; gap?: number }) {
  return (
    <View style={{ gap }}>
      <View style={s.sectionHead}>
        <Txt v="section">{title}</Txt>
        {right}
      </View>
      {children}
    </View>
  );
}

export function LinkText({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} hitSlop={12} style={({ pressed }) => pressed && { opacity: 0.6 }}>
      <Text style={s.link}>{label}</Text>
    </Pressable>
  );
}

// Khung màn: vùng cuộn + thanh hành động dưới cố định (nếu có).
export function Screen({
  header,
  footer,
  children,
  edges = ['top'],
  maxWidth = 720,
  scrollRef,
}: {
  header?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  edges?: ('top' | 'bottom')[];
  maxWidth?: number;
  scrollRef?: Ref<ScrollView>;
}) {
  return (
    <SafeAreaView edges={footer ? ['top', 'bottom'] : edges} style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={[s.column, { maxWidth }]}>
        {header}
        <ScrollView ref={scrollRef} contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
          {children}
        </ScrollView>
        {footer && <View style={s.footer}>{footer}</View>}
      </View>
    </SafeAreaView>
  );
}

export const s = StyleSheet.create({
  btn: {
    minHeight: 56,
    borderRadius: radius.button,
    paddingHorizontal: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  btnMd: { minHeight: 44, borderRadius: radius.chip, paddingHorizontal: 16, gap: 8 },
  btnSecondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  btnLabel: { fontFamily: fonts.bold, fontSize: 16 },
  iconBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chip: {
    paddingVertical: 9,
    paddingHorizontal: 14,
    borderRadius: radius.pill,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  chipSmall: { paddingVertical: 7, paddingHorizontal: 12, borderRadius: radius.chip },
  chipText: { fontFamily: fonts.semibold, fontSize: 13 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.card,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 16,
    paddingHorizontal: 18,
  },
  notice: { flexDirection: 'row', gap: 11, padding: 13, paddingHorizontal: 14, borderRadius: radius.pill, borderWidth: 1 },
  noticeText: { fontFamily: fonts.medium, fontSize: 12, lineHeight: 18 },
  sectionHead: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' },
  link: { fontFamily: fonts.semibold, fontSize: 13, color: colors.primary },
  column: { flex: 1, width: '100%', alignSelf: 'center' },
  scroll: { paddingHorizontal: 20, paddingTop: 6, paddingBottom: 28, gap: 18 },
  footer: {
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 16,
    borderTopWidth: 1,
    borderTopColor: colors.borderSoft,
    backgroundColor: colors.bg,
  },
  row: { flexDirection: 'row', alignItems: 'center' },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  thumb: {
    width: 56,
    height: 56,
    borderRadius: radius.chip,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
