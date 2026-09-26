# Design Spec — Bếp AI (React Native + Expo, PWA-ready)

> File này là nguồn chân lý về UI cho dự án. Claude Code đọc file này trước khi viết bất kỳ component nào.
> Mockup gốc: 8 artboard HTML trong `design/artboards/` (mở bằng trình duyệt để xem).

## 1. Design tokens

```js
export const colors = {
  bg:         '#FBF8F2', // nền chính (kem ấm)
  surface:    '#FFFFFF', // thẻ, card
  surfaceAlt: '#F0EADC', // chip, ô phụ
  border:     '#E8E2D6',
  borderSoft: '#EFE9DE',

  ink:        '#16150F', // chữ chính
  muted:      '#6B6558', // chữ phụ (đạt 4.5:1 trên nền kem)

  primary:    '#2E6B4A', // xanh thảo mộc — CTA, trạng thái hợp lệ
  primaryDark:'#235239',
  primarySoft:'#F1F5EE', // nền badge an toàn
  primaryLine:'#D6E2D0',

  warn:       '#8A3F13', // cảnh báo (sắp hết hạn, độ tin cậy thấp)
  warnBg:     '#FBEDE3',
  warnLine:   '#E8C3A6',
  danger:     '#7A2E12', // dị ứng, xoá

  camBg:      '#14160F', // nền màn camera
  camSurface: '#20241A',
};

export const radius  = { chip: 14, card: 20, cardLg: 22, pill: 16, button: 18, full: 999 }; // card 20 = khớp artboard
export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 28 };
```

## 2. Typography

- **Display** (tiêu đề, số liệu lớn): `Fraunces` — weight 500/600
- **Body / UI**: `Plus Jakarta Sans` — weight 400/500/600/700
- Expo: cài bằng `expo-font` + `@expo-google-fonts/fraunces`, `@expo-google-fonts/plus-jakarta-sans`

| Vai trò | Font | Size | Weight |
|---|---|---|---|
| Tiêu đề màn hình | Fraunces | 26–32 | 600 |
| Số dinh dưỡng lớn | Fraunces | 34–40 | 600 |
| Tên món trong list | Jakarta | 15 | 700 |
| Body | Jakarta | 14 | 500 |
| Nhãn phụ / caption | Jakarta | 11–12 | 600, màu `muted` |
| Nhãn section uppercase | Jakarta | 12 | 700, letter-spacing 0.05em |

## 3. Quy tắc bắt buộc

- Mọi vùng chạm (button, tab, checkbox row) **tối thiểu 44×44px**.
- Mỗi màn chỉ có **một CTA chính** (nền `primary`, chữ trắng, min-height 56, radius 18).
- Nút phụ: nền trắng, viền `border`, chữ `ink`.
- Thanh tab dưới cùng: 4 mục (Tủ lạnh / Chụp / Đã lưu / Đang nấu), cao 84, mục active dùng màu `primary`.
- Không dùng emoji làm icon — dùng icon stroke (`lucide-react-native`), stroke-width 1.7–1.8.
- Không gradient nền, không viền trái trang trí trên card.
- Mọi icon-only button phải có `accessibilityLabel`.

## 4. Các màn hình

| # | File artboard | Màn hình | Ghi chú triển khai |
|---|---|---|---|
| 1 | `Main.dc.html` | Trang chủ / Tủ lạnh | CTA lớn mở camera; chip nguyên liệu; card nhật ký calo hôm nay |
| 2 | `Camera.dc.html` | Chụp nguyên liệu | `expo-camera`; khung ngắm 4 góc; chip nhận diện kèm % confidence |
| 3 | `Confirm.dc.html` | Xác nhận + bộ lọc | **Quan trọng**: chế độ ăn + dị ứng là ràng buộc cứng, đưa vào WHERE của query, KHÔNG nhét vào prompt |
| 4 | `Recipe.dc.html` | Kết quả công thức | Công thức + dinh dưỡng hiện ngay; ảnh AI là thẻ nét đứt cuối trang, lazy, bấm mới gọi |
| 4b | `RecipeImage.dc.html` | Sau khi tạo ảnh AI | Khung ảnh 350×236, radius 22; nhãn "Ảnh do AI dựng" đè góc dưới trái; nút Tạo lại / Ẩn ảnh |
| 5 | `Steps.dc.html` | Chế độ nấu | Progress bar theo bước; timer; cảnh báo nhiệt độ/thời gian tối thiểu không cho rút ngắn |
| 6 | `Saved.dc.html` | Đã lưu | Mỗi item có Mở / Sao chép / Xoá; xem được offline |
| 7 | `Desktop.dc.html` | Web màn rộng | Sidebar 236px + 2 cột; dropzone thay cho camera; có ô mời cài PWA |

## 5. Ghi chú cho PWA

- Một codebase Expo, build web bằng `react-native-web` (`npx expo export --platform web`).
- Breakpoint desktop ≥ 1024px: đổi tab bar dưới thành sidebar trái (xem `Desktop.dc.html`).
- Cần `manifest.json` (name, icons 192/512, `display: standalone`, `theme_color: #2E6B4A`) + service worker cache công thức đã lưu để xem offline.

## 6. Việc cho Claude Code

1. Dựng `theme.ts` từ mục 1 + 2.
2. Tạo component dùng lại: `Button`, `Chip`, `Card`, `BottomTabBar`, `NutritionRow`, `IngredientRow`, `SafetyBadge`.
3. Dựng lần lượt màn 1 → 6 theo artboard, dùng dữ liệu mock trước, chưa nối API.
4. Nối API sau khi UI chạy ổn.
