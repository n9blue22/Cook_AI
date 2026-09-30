import { router } from 'expo-router';
import { CookingPot, X } from 'lucide-react-native';
import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Button, Card, Chip, IconButton, LinkText, SafetyBadge, Screen, s as ui, Txt } from '../components/ui';
import { mealLogFor } from '../lib/recipes';
import { useStore } from '../lib/store';
import { useSubmit } from '../lib/useSubmit';
import { artboard, colors, fonts, iconStroke } from '../theme';

const TICK_MS = 1000;
const LOG_FAILED = 'Chưa ghi được vào nhật ký — thử lại';
const NO_NUTRITION_NOTE = 'Món này chưa tính được dinh dưỡng nên không ghi vào nhật ký';

const mmss = (sec: number) => `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`;

// Hẹn giờ của 1 bước. Màn Nấu gắn key theo món + bước → sang bước khác là state mới, không cần reset trong effect.
// Đếm theo mốc kết thúc (endsAt) thay vì trừ 1 mỗi giây: tab bị trình duyệt làm chậm vẫn không đếm sai.
function StepTimer({ seconds, onDone }: { seconds: number; onDone: () => void }) {
  const [left, setLeft] = useState(seconds);
  const [endsAt, setEndsAt] = useState<number | null>(null); // null = đang dừng

  useEffect(() => {
    if (endsAt === null) return;
    const tick = setInterval(() => {
      const remaining = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
      setLeft(remaining);
      if (remaining > 0) return;
      setEndsAt(null);
      onDone();
    }, TICK_MS);
    return () => clearInterval(tick);
  }, [endsAt, onDone]);

  const running = endsAt !== null;
  return (
    <Card style={st.timer}>
      <View style={{ flex: 1, gap: 3 }}>
        <Text style={st.timerLabel}>Hẹn giờ</Text>
        <Text style={[st.timerVal, left === 0 && { color: colors.primary }]} accessibilityLiveRegion="polite">
          {left === 0 ? 'Xong' : mmss(left)}
        </Text>
      </View>
      {left > 0 ? (
        <Button
          size="md"
          style={st.timerBtn}
          labelStyle={{ fontSize: 15 }}
          label={running ? 'Tạm dừng' : left < seconds ? 'Tiếp tục' : 'Bắt đầu'}
          onPress={() => setEndsAt(running ? null : Date.now() + left * 1000)}
        />
      ) : (
        <Button size="md" kind="secondary" label="Đặt lại" onPress={() => setLeft(seconds)} />
      )}
    </Card>
  );
}

export default function Cook() {
  const store = useStore();
  const r = store.cooking && store.findRecipe(store.cooking.id);
  const i = store.cooking?.step ?? 0;
  const step = r?.steps[i];
  const [safeSteps, setSafeSteps] = useState<number[]>([]);
  const finishing = useSubmit(LOG_FAILED);
  const markSafe = useCallback(() => setSafeSteps((done) => (done.includes(i) ? done : [...done, i])), [i]);

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
          <Txt v="caption" style={{ fontSize: 13, textAlign: 'center' }}>Chọn một công thức rồi bấm “Bắt đầu nấu”.</Txt>
          <Button label="Tìm món để nấu" onPress={() => router.replace('/')} style={{ alignSelf: 'stretch' }} />
        </View>
      </Screen>
    );
  }

  const safeDone = !step.safetyMinSec || safeSteps.includes(i);
  const last = i === r.steps.length - 1;
  const nextSafety = r.steps[i + 1]?.safetyMinSec;
  // Không cho kết thúc sớm khi còn bước nấu chín bắt buộc phía sau.
  const canFinishEarly = safeDone && !r.steps.slice(i + 1).some((x) => x.safetyMinSec);
  const meal = mealLogFor(r);
  const kcalNote = meal ? ` · ghi ${Math.round(meal.kcal)} kcal` : '';
  const finish = () =>
    finishing.run(async () => {
      await store.finishCooking(r);
      router.replace('/');
    });

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
          {!meal && (last || canFinishEarly) && (
            <Txt v="caption" style={{ textAlign: 'center' }}>{NO_NUTRITION_NOTE}</Txt>
          )}
          {finishing.error && (
            <Txt v="caption" style={{ color: colors.danger, textAlign: 'center' }} accessibilityRole="alert">
              {finishing.error}
            </Txt>
          )}
          <View style={[ui.row, { gap: 10 }]}>
            <Button kind="secondary" style={{ paddingHorizontal: 20 }} label="Trước" disabled={i === 0} onPress={() => store.setStep(i - 1)} />
            <Button
              style={{ flex: 1 }}
              label={last ? (finishing.busy ? 'Đang ghi…' : `Hoàn tất${kcalNote}`) : 'Bước tiếp theo'}
              disabled={!safeDone || finishing.busy}
              onPress={() => (last ? finish() : store.setStep(i + 1))}
            />
          </View>
          {!last && canFinishEarly && (
            <View style={{ alignItems: 'center', paddingVertical: 10 }}>
              <LinkText
                style={{ fontFamily: fonts.bold }}
                label={finishing.busy ? 'Đang ghi…' : meal ? `Đã nấu xong — ghi ${Math.round(meal.kcal)} kcal vào nhật ký` : 'Đã nấu xong'}
                onPress={finish}
              />
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

        {!!step.timerSec && <StepTimer key={`${r.id}:${i}`} seconds={step.timerSec} onDone={markSafe} />}

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
  timerBtn: { minHeight: 48, paddingHorizontal: 22, borderRadius: 16 }, // Steps.dc.html
  timerVal: { fontFamily: fonts.display, fontSize: 36, lineHeight: 36, color: colors.ink, fontVariant: ['tabular-nums'] },
  usesLabel: { fontFamily: fonts.bold, fontSize: 13, color: colors.muted },
});
