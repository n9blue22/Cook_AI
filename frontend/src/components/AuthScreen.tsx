import { Check, Circle } from 'lucide-react-native';
import { ReactNode } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { isPasswordTooLong, PASSWORD_TOO_LONG_MESSAGE, passwordRules } from '../lib/password';
import { colors, fonts, iconStroke } from '../theme';
import { BrandMark } from './BrandMark';
import { Card, SafetyBadge, Txt } from './ui';

type AuthScreenProps = {
  title: string;
  subtitle: string;
  notice?: string | null; // thông báo thành công (nền xanh)
  error?: string | null; // lỗi từ server (nền cam)
  footer: ReactNode; // CTA chính + link phụ
  children: ReactNode;
};

// Khung chung cho đăng nhập / đăng ký / quên + đặt lại mật khẩu:
// Thiết kế dạng Card trung tâm hiện đại, form và nút hành động liền mạch.
export function AuthScreen({ title, subtitle, notice, error, footer, children }: AuthScreenProps) {
  return (
    <SafeAreaView edges={['top', 'bottom']} style={st.safeArea}>
      <ScrollView
        contentContainerStyle={st.scroll}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={st.container}>
          <Card style={st.card}>
            <View style={st.brandWrap}>
              <BrandMark />
            </View>

            <View style={st.header}>
              <Txt v="title" style={st.title}>{title}</Txt>
              <Txt v="body" style={st.subtitle}>
                {subtitle}
              </Txt>
            </View>

            {!!notice && <SafetyBadge>{notice}</SafetyBadge>}
            {!!error && <SafetyBadge tone="warn">{error}</SafetyBadge>}

            <View style={st.form}>{children}</View>

            {footer && <View style={st.footer}>{footer}</View>}
          </Card>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

// Luật mật khẩu hiện trực tiếp khi gõ (cùng luật backend) — biết thiếu gì trước khi bấm.
export function PasswordChecklist({ password }: { password: string }) {
  const rules = passwordRules(password);
  const allOk = password.length > 0 && rules.every((r) => r.ok) && !isPasswordTooLong(password);
  return (
    <View
      style={[
        st.rulesCard,
        allOk && { backgroundColor: colors.primarySoft, borderColor: colors.primaryLine },
      ]}
      accessibilityLabel="Yêu cầu mật khẩu"
    >
      <Text style={[st.rulesTitle, allOk && { color: colors.primary }]}>
        {allOk ? '✓ Mật khẩu đạt độ an toàn' : 'Yêu cầu bảo mật mật khẩu:'}
      </Text>
      <View style={{ gap: 5 }}>
        {rules.map((rule) => {
          const Icon = rule.ok ? Check : Circle;
          return (
            <View key={rule.label} style={st.rule}>
              <Icon size={13} color={rule.ok ? colors.primary : colors.muted} strokeWidth={iconStroke} />
              <Text style={[st.ruleText, rule.ok && { color: colors.primary, fontFamily: fonts.semibold }]}>
                {rule.label}
              </Text>
            </View>
          );
        })}
        {isPasswordTooLong(password) && (
          <Text style={[st.ruleText, { color: colors.warn }]} role="alert">
            {PASSWORD_TOO_LONG_MESSAGE}
          </Text>
        )}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 32,
    paddingHorizontal: 20,
  },
  container: {
    width: '100%',
    maxWidth: 440,
  },
  card: {
    gap: 18,
    padding: 26,
    borderRadius: 24,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    boxShadow: '0 8px 30px rgba(26, 33, 28, 0.05)',
    elevation: 3,
  },
  brandWrap: {
    alignItems: 'center',
    marginBottom: 2,
  },
  header: {
    gap: 6,
    alignItems: 'center',
  },
  title: {
    fontSize: 24,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 13,
    color: colors.muted,
    textAlign: 'center',
    lineHeight: 19,
  },
  form: {
    gap: 14,
  },
  footer: {
    marginTop: 4,
    gap: 12,
  },
  rulesCard: {
    padding: 12,
    borderRadius: 14,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    gap: 8,
  },
  rulesTitle: {
    fontFamily: fonts.semibold,
    fontSize: 12,
    color: colors.muted,
  },
  rule: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  ruleText: { fontFamily: fonts.medium, fontSize: 12, color: colors.muted },
});
