import { Tabs } from 'expo-router';
import { useWindowDimensions } from 'react-native';
import { BottomTabBar } from '../../components/BottomTabBar';
import { colors, DESKTOP_MIN } from '../../theme';

export default function TabsLayout() {
  const desktop = useWindowDimensions().width >= DESKTOP_MIN;
  return (
    <Tabs
      tabBar={(p) => <BottomTabBar {...p} desktop={desktop} />}
      screenOptions={{
        headerShown: false,
        tabBarPosition: desktop ? 'left' : 'bottom',
        sceneStyle: { backgroundColor: colors.bg },
        animation: 'fade',
      }}
    >
      <Tabs.Screen name="index" />
      <Tabs.Screen name="saved" />
    </Tabs>
  );
}
