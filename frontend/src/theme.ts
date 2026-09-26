// Tokens từ design/design-spec.md — không thêm màu/font ngoài file này.
import type { TextStyle } from 'react-native';

export const colors = {
  bg: '#FBF8F2',
  surface: '#FFFFFF',
  surfaceAlt: '#F0EADC',
  border: '#E8E2D6',
  borderSoft: '#EFE9DE',

  ink: '#16150F',
  muted: '#6B6558',

  primary: '#2E6B4A',
  primaryDark: '#235239',
  primarySoft: '#F1F5EE',
  primaryLine: '#D6E2D0',

  warn: '#8A3F13',
  warnBg: '#FBEDE3',
  warnLine: '#E8C3A6',
  danger: '#7A2E12',

  camBg: '#14160F',
  camSurface: '#20241A',
};

// Màu phụ lấy nguyên từ artboard (chữ trên nền xanh/cam nhạt, dải tiến độ…).
export const artboard = {
  onPrimarySoft: '#2A3B2E',
  onPrimarySoftMuted: '#4A5C4D',
  onWarnBg: '#6B3211',
  onPrimaryMuted: '#D5E5DB',
  track: '#EFEAE0',
  trackStep: '#E4DDCE',
  carbs: '#9BB8A4',
  fat: '#C4622D',
  dashed: '#D6CDBC',
  dropLine: '#C9C0AE',
  unsure: '#C9A880',
  dangerLine: '#E6C9BD',
  sidebarInk: '#4A4538',
  cam: { chip: '#262A1E', line: '#3A3F2E', ink: '#E4E9D8', dim: '#A9AE9B', lowChip: '#4A4F3C' },
};

export const radius = { chip: 14, card: 20, cardLg: 22, pill: 16, button: 18, full: 999 };
export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 28 };

export const fonts = {
  display: 'Fraunces_600SemiBold',
  displayMedium: 'Fraunces_500Medium',
  regular: 'PlusJakartaSans_400Regular',
  medium: 'PlusJakartaSans_500Medium',
  semibold: 'PlusJakartaSans_600SemiBold',
  bold: 'PlusJakartaSans_700Bold',
};

// Chữ / icon trắng trên nền primary, danger, ink, camera (spec mục 3: "CTA nền primary, chữ trắng").
export const onColor = '#FFFFFF';

// Vai trò chữ theo design-spec mục 2. Key = variant của <Txt> (components/ui.tsx).
export const typography = {
  title: { fontFamily: fonts.display, fontSize: 26, lineHeight: 30, color: colors.ink }, // Tiêu đề màn hình
  display: { fontFamily: fonts.display, fontSize: 40, lineHeight: 42, color: colors.ink }, // Số dinh dưỡng lớn
  item: { fontFamily: fonts.bold, fontSize: 15, color: colors.ink }, // Tên món trong list
  section: { fontFamily: fonts.bold, fontSize: 15, color: colors.ink }, // Tiêu đề khối (cùng cỡ tên món)
  body: { fontFamily: fonts.medium, fontSize: 14, lineHeight: 21, color: colors.ink }, // Body
  bodyStrong: { fontFamily: fonts.bold, fontSize: 14, color: colors.ink },
  caption: { fontFamily: fonts.semibold, fontSize: 12, color: colors.muted }, // Nhãn phụ / caption
  overline: {
    // Nhãn section uppercase, letter-spacing 0.05em
    fontFamily: fonts.bold,
    fontSize: 12,
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    color: colors.muted,
  },
} satisfies Record<string, TextStyle>;

export const iconStroke = 1.8;
export const DESKTOP_MIN = 1024;
