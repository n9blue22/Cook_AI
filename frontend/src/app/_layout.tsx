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
  const done = (fontsLoaded || !!fontError) && ready;

  useEffect(() => {
    if (done) SplashScreen.hideAsync();
  }, [done]);

  if (!done) return null;
  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg }, animation: 'slide_from_right' }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="camera" options={{ animation: 'fade_from_bottom', contentStyle: { backgroundColor: colors.camBg } }} />
      </Stack>
    </>
  );
}

export default function Layout() {
  return (
    <StoreProvider>
      <Root />
    </StoreProvider>
  );
}
