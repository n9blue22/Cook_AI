import { Stack } from 'expo-router';
import { colors } from '../../theme';

// Bị chặn quay lại khi đã đăng nhập → vào nhóm này luôn bắt đầu ở /login
export const unstable_settings = { initialRouteName: 'login' };

// Màn cho người CHƯA đăng nhập (root _layout chặn bằng Stack.Protected).
export default function AuthLayout() {
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }} />;
}
