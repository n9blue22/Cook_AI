// Tokens từ design/design-spec.md — không thêm màu/font ngoài file này.
import type { TextStyle } from 'react-native';

export const colors = {
  bg: '#F8F9F6', // Nền kem sáng thoáng, dịu mắt
  surface: '#FFFFFF', // Thẻ và bề mặt màu trắng tinh khôi
  surfaceAlt: '#F1F4F0', // Nền phụ nhẹ nhàng
  border: '#E5E9E2', // Viền mỏng thanh mảnh
  borderSoft: '#EDF1EB', // Viền siêu mềm

  ink: '#1A211C', // Màu chữ đen than xanh ấm áp, dễ đọc
  muted: '#667067', // Màu chữ phụ xám rêu nhẹ nhàng

  primary: '#2D6A4F', // Xanh ngọc lục bảo / xô thơm tự nhiên, dịu mắt
  primaryDark: '#20503B',
  primarySoft: '#EBF4EE', // Nền xanh pastel mát mẻ
  primaryLine: '#C8E0D2',

  warn: '#96481E', // Cam nâu đất ấm áp
  warnBg: '#FCF2EB', // Nền cam pastel nhẹ
  warnLine: '#F3D6C3',
  danger: '#872C15',

  camBg: '#121613',
  camSurface: '#1D241F',
};

// Màu phụ lấy nguyên từ artboard (chữ trên nền xanh/cam nhạt, dải tiến độ…).
export const artboard = {
  onPrimarySoft: '#1F3F2E',
  onPrimarySoftMuted: '#405B4C',
  onWarnBg: '#6E3211',
  onPrimaryMuted: '#D0E4D7',
  track: '#E8ECE6',
  trackStep: '#DCE2DA',
  carbs: '#82B696',
  fat: '#D47644',
  dashed: '#D3DDD4',
  dropLine: '#C5D3C7',
  unsure: '#C49F75',
  dangerLine: '#E8CCC2',
  sidebarInk: '#3E4940',
  cam: { chip: '#242D26', line: '#37433A', ink: '#E2EBE4', dim: '#9CAAA0', lowChip: '#455549' },
};

// Nền gradient màn đăng nhập/đăng ký (AuthBackground) — chỉ dùng làm stopColor, không dùng cho chữ.
export const authGradient = {
  aura: '#D5EADB', // ánh ngọc góc trên (desktop + mobile)
  auraMid: '#E2F2E7',
  auraSoft: '#EDF6F0',
  mobileAuraMid: '#E4F3E9',
  mobileAuraSoft: '#F1F7F3',
  meshGreen: '#529977', // dải chéo desktop
  meshMint: '#B8DEC8',
  warm: '#F7EFE8', // ánh kem ấm góc dưới
  warmSoft: '#FAF4EF',
};

export const radius = { chip: 16, card: 22, cardLg: 26, pill: 20, button: 20, full: 999 };
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
