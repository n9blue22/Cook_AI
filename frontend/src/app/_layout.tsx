import { Fraunces_500Medium, Fraunces_600SemiBold } from '@expo-google-fonts/fraunces';
import {
  PlusJakartaSans_400Regular,
  PlusJakartaSans_500Medium,
  PlusJakartaSans_600SemiBold,
  PlusJakartaSans_700Bold,
} from '@expo-google-fonts/plus-jakarta-sans';
import { useFonts } from 'expo-font';
import { SplashScreen, Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { AuthProvider, useAuth } from '../lib/auth';
import { StoreProvider, useStore } from '../lib/store';
import { colors } from '../theme';

SplashScreen.preventAutoHideAsync();

function Root() {
  const [fontsLoaded, fontError] = useFonts({
    Fraunces_500Medium,
    Fraunces_600SemiBold,
    PlusJakartaSans_400Regular,
    PlusJakartaSans_500Medium,
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
  });
  const { ready } = useStore();
  const { status } = useAuth();
  const done = (fontsLoaded || !!fontError) && ready && status !== 'loading'; // giữ splash tới khi biết đã đăng nhập chưa
  const signedIn = status === 'signedIn';

  useEffect(() => {
    if (done) SplashScreen.hideAsync();
  }, [done]);

  if (!done) return null;
  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg }, animation: 'slide_from_right' }}>
        {/* Khai báo đủ mọi màn: màn không khai báo sẽ bị expo-router tự thêm NGOÀI lớp chặn */}
        <Stack.Protected guard={signedIn}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="camera" options={{ animation: 'fade_from_bottom', contentStyle: { backgroundColor: colors.camBg } }} />
          <Stack.Screen name="confirm" />
          <Stack.Screen name="cook" />
          <Stack.Screen name="recipe/[id]" />
        </Stack.Protected>
        <Stack.Protected guard={!signedIn}>
          <Stack.Screen name="(auth)" />
        </Stack.Protected>
        {/* Mở từ link email khi chưa đăng nhập */}
        <Stack.Screen name="reset-password" />
      </Stack>
    </>
  );
}

export default function Layout() {
  return (
    <AuthProvider>
      <StoreProvider>
        <Root />
      </StoreProvider>
    </AuthProvider>
  );
}
