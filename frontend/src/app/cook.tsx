import { router } from 'expo-router';
import { CookingPot, X } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Button, Card, Chip, IconButton, LinkText, SafetyBadge, Screen, s as ui, Txt } from '../components/ui';
import { getRecipe } from '../lib/recipes';
import { useStore } from '../lib/store';
import { artboard, colors, fonts, iconStroke } from '../theme';

const mmss = (sec: number) => `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`;

export default function Cook() {
  const store = useStore();
  const r = store.cooking && getRecipe(store.cooking.id);
  const i = store.cooking?.step ?? 0;
  const step = r?.steps[i];

  const [left, setLeft] = useState(step?.timerSec ?? 0);
  const [running, setRunning] = useState(false);
  const [safeSteps, setSafeSteps] = useState<number[]>([]);
  const safeDone = !step?.safetyMinSec || safeSteps.includes(i);

  useEffect(() => {
    setLeft(step?.timerSec ?? 0);
    setRunning(false);
  }, [r?.id, i]);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => {
      setLeft((l) => {
        if (l <= 1) {
          setRunning(false);
          setSafeSteps((d) => [...d, i]);
          return 0;
        }
        return l - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [running, i]);

  const exit = () => (router.canGoBack() ? router.back() : router.replace('/'));

  if (!r || !step) {
    return (
      <Screen
        header={
          <View style={st.header}>
            <IconButton icon={X} label="Đóng" onPress={exit} />
          </View>
        }
      >
        <View style={{ alignItems: 'center', gap: 14, paddingTop: 60 }}>
          <View style={[ui.thumb, { width: 72, height: 72, borderRadius: 22 }]}>
            <CookingPot size={32} color={colors.muted} strokeWidth={iconStroke} />
          </View>
          <Txt v="title" style={{ fontSize: 22, textAlign: 'center' }}>Chưa nấu món nào</Txt>
          <Txt v="caption" style={{ fontSize: 13, textAlign: 'center' }}>Chọn một công thức rồi bấm "Bắt đầu nấu".</Txt>
          <Button label="Tìm món để nấu" onPress={() => router.replace('/')} style={{ alignSelf: 'stretch' }} />
        </View>
      </Screen>
    );
  }

  const last = i === r.steps.length - 1;
  const nextSafety = r.steps[i + 1]?.safetyMinSec;
  // Không cho kết thúc sớm khi còn bước nấu chín bắt buộc phía sau.
  const canFinishEarly = safeDone && !r.steps.slice(i + 1).some((x) => x.safetyMinSec);
  const finish = () => {
    store.finishCooking();
    router.replace('/');
  };

  return (
    <Screen
      header={
        <View>
          <View style={st.header}>
            <IconButton icon={X} label="Thoát chế độ nấu" onPress={exit} />
            <Text style={st.headTitle} numberOfLines={1}>{r.name}</Text>
            <View style={{ width: 44 }} />
          </View>
          <View style={st.progress} accessibilityRole="progressbar" accessibilityValue={{ min: 1, max: r.steps.length, now: i + 1 }}>
            {r.steps.map((_, k) => (
              <View key={k} style={[st.seg, k <= i && { backgroundColor: colors.primary }]} />
            ))}
          </View>
        </View>
      }
      footer={
        <View style={{ gap: 10 }}>
          <View style={[ui.row, { gap: 10 }]}>
            <Button kind="secondary" label="Trước" disabled={i === 0} onPress={() => store.setStep(i - 1)} />
            <Button
              style={{ flex: 1 }}
              label={last ? `Hoàn tất · ghi ${r.kcal} kcal` : 'Bước tiếp theo'}
              disabled={!safeDone}
              onPress={() => (last ? finish() : store.setStep(i + 1))}
            />
          </View>
          {!last && canFinishEarly && (
            <View style={{ alignItems: 'center', paddingVertical: 6 }}>
              <LinkText label={`Đã nấu xong — ghi ${r.kcal} kcal vào nhật ký`} onPress={finish} />
            </View>
          )}
        </View>
      }
    >
      <View style={{ gap: 22, paddingTop: 20 }}>
        <Txt v="overline">
          Bước {i + 1} / {r.steps.length}
        </Txt>
        <Text style={st.stepText}>{step.text}</Text>

        {!!step.timerSec && (
          <Card style={st.timer}>
            <View style={{ flex: 1, gap: 3 }}>
              <Text style={st.timerLabel}>Hẹn giờ</Text>
              <Text style={[st.timerVal, left === 0 && { color: colors.primary }]} accessibilityLiveRegion="polite">
                {left === 0 ? 'Xong' : mmss(left)}
              </Text>
            </View>
            {left > 0 ? (
              <Button size="md" style={{ minHeight: 48, paddingHorizontal: 22 }} label={running ? 'Tạm dừng' : left < step.timerSec ? 'Tiếp tục' : 'Bắt đầu'} onPress={() => setRunning((x) => !x)} />
            ) : (
              <Button size="md" kind="secondary" label="Đặt lại" onPress={() => setLeft(step.timerSec!)} />
            )}
          </Card>
        )}

        {step.safetyMinSec ? (
          <SafetyBadge tone="warn">
            {safeDone
              ? 'Đã đủ thời gian nấu chín an toàn — có thể sang bước tiếp.'
              : `Bước này cần nấu tối thiểu ${mmss(step.safetyMinSec)} để chín an toàn — chạy hết hẹn giờ mới sang bước tiếp được.`}
          </SafetyBadge>
        ) : nextSafety ? (
          <SafetyBadge tone="warn">
            Bước sau cần nấu đủ {mmss(nextSafety)} đến khi chín hẳn — hệ thống sẽ không cho rút ngắn thời gian dưới mức an toàn.
          </SafetyBadge>
        ) : null}

        {!!step.uses?.length && (
          <View style={{ gap: 8 }}>
            <Text style={st.usesLabel}>Dùng ở bước này</Text>
            <View style={ui.wrap}>
              {step.uses.map((u) => (
                <Chip key={u} label={u} />
              ))}
            </View>
          </View>
        )}
      </View>
    </Screen>
  );
}

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingHorizontal: 20, paddingTop: 24, paddingBottom: 14 },
  headTitle: { flex: 1, textAlign: 'center', fontFamily: fonts.bold, fontSize: 14, color: colors.ink },
  progress: { flexDirection: 'row', gap: 6, paddingHorizontal: 20 },
  seg: { flex: 1, height: 5, borderRadius: 3, backgroundColor: artboard.trackStep },
  stepText: { fontFamily: fonts.displayMedium, fontSize: 27, lineHeight: 36, color: colors.ink },
  timer: { flexDirection: 'row', alignItems: 'center', gap: 16, padding: 18 },
  timerLabel: { fontFamily: fonts.bold, fontSize: 12, color: colors.muted },
  timerVal: { fontFamily: fonts.display, fontSize: 36, lineHeight: 40, color: colors.ink, fontVariant: ['tabular-nums'] },
  usesLabel: { fontFamily: fonts.bold, fontSize: 13, color: colors.muted },
});
