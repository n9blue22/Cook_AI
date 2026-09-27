import { Check, Circle } from 'lucide-react-native';
import { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { passwordRules } from '../lib/password';
import { colors, fonts, iconStroke } from '../theme';
import { BrandMark } from './BrandMark';
import { SafetyBadge, Screen, Txt } from './ui';

type AuthScreenProps = {
  title: string;
  subtitle: string;
  notice?: string | null; // thông báo thành công (nền xanh)
  error?: string | null; // lỗi từ server (nền cam)
  footer: ReactNode; // CTA chính + link phụ
  children: ReactNode;
};

// Khung chung cho đăng nhập / đăng ký / quên + đặt lại mật khẩu: logo, tiêu đề, form, 1 CTA cố định dưới.
export function AuthScreen({ title, subtitle, notice, error, footer, children }: AuthScreenProps) {
  return (
    <Screen maxWidth={480} footer={footer} contentStyle={{ paddingTop: 28, gap: 20 }}>
      <BrandMark />
      <View style={{ gap: 6 }}>
        <Txt v="title">{title}</Txt>
        <Txt v="body" style={{ color: colors.muted }}>
          {subtitle}
        </Txt>
      </View>
      {!!notice && <SafetyBadge>{notice}</SafetyBadge>}
      {!!error && <SafetyBadge tone="warn">{error}</SafetyBadge>}
      <View style={{ gap: 14 }}>{children}</View>
    </Screen>
  );
}

// Luật mật khẩu hiện trực tiếp khi gõ (cùng luật backend) — biết thiếu gì trước khi bấm.
export function PasswordChecklist({ password }: { password: string }) {
  return (
    <View style={{ gap: 4 }} accessibilityLabel="Yêu cầu mật khẩu">
      {passwordRules(password).map((rule) => {
        const Icon = rule.ok ? Check : Circle;
        return (
          <View key={rule.label} style={st.rule}>
            <Icon size={14} color={rule.ok ? colors.primary : colors.muted} strokeWidth={iconStroke} />
            <Text style={[st.ruleText, rule.ok && { color: colors.primary }]}>{rule.label}</Text>
          </View>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  rule: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  ruleText: { fontFamily: fonts.medium, fontSize: 12, color: colors.muted },
});
