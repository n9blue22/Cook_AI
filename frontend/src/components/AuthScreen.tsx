import { Camera, Check, ChefHat, Circle, Sparkles, UtensilsCrossed } from 'lucide-react-native';
import { ReactNode, useEffect, useRef } from 'react';
import { Animated, Platform, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';
import { isPasswordTooLong, PASSWORD_TOO_LONG_MESSAGE, passwordRules } from '../lib/password';
import { colors, DESKTOP_MIN, fonts, iconStroke, radius } from '../theme';
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

// ─── Nền Mesh Gradient Hiện Đại & Chuyên Nghiệp ────────────────────────────────
// Phong cách Ambient Luminous hiện đại (Linear/Apple/Airbnb):
// Ánh sáng ngọc lục bảo và kem ấm tự nhiên, chuyển sắc mượt mà không đốm tròn loang lổ.
function AuthBackground({ isDesktop }: { isDesktop: boolean }) {
  if (isDesktop) {
    return (
      <View style={StyleSheet.absoluteFill} pointerEvents="none" aria-hidden>
        <Svg width="100%" height="100%" style={StyleSheet.absoluteFill}>
          <Defs>
            {/* Lớp ánh ngọc lục bảo thanh nhã từ góc trên-trái lan toả */}
            <LinearGradient id="bgAuraLeft" x1="0%" y1="0%" x2="70%" y2="70%">
              <Stop offset="0%" stopColor="#D5EADB" stopOpacity="0.85" />
              <Stop offset="25%" stopColor="#E2F2E7" stopOpacity="0.65" />
              <Stop offset="55%" stopColor="#EDF6F0" stopOpacity="0.4" />
              <Stop offset="85%" stopColor="#F8F9F6" stopOpacity="0" />
            </LinearGradient>

            {/* Dải mesh chéo thanh lịch tạo độ sâu đa chiều phong cách hiện đại */}
            <LinearGradient id="bgMeshDiagonal" x1="10%" y1="0%" x2="90%" y2="100%">
              <Stop offset="0%" stopColor="#2D6A4F" stopOpacity="0.08" />
              <Stop offset="30%" stopColor="#529977" stopOpacity="0.05" />
              <Stop offset="70%" stopColor="#B8DEC8" stopOpacity="0.08" />
              <Stop offset="100%" stopColor="#F8F9F6" stopOpacity="0" />
            </LinearGradient>

            {/* Ánh ấm dịu mắt ở góc dưới tạo cảm giác ấm cúng tự nhiên cho căn bếp */}
            <LinearGradient id="bgWarmRight" x1="100%" y1="100%" x2="50%" y2="50%">
              <Stop offset="0%" stopColor="#F7EFE8" stopOpacity="0.7" />
              <Stop offset="50%" stopColor="#FAF4EF" stopOpacity="0.35" />
              <Stop offset="100%" stopColor="#F8F9F6" stopOpacity="0" />
            </LinearGradient>
          </Defs>
          <Rect width="100%" height="100%" fill="#F8F9F6" />
          <Rect width="100%" height="100%" fill="url(#bgAuraLeft)" />
          <Rect width="100%" height="100%" fill="url(#bgMeshDiagonal)" />
          <Rect width="100%" height="100%" fill="url(#bgWarmRight)" />
        </Svg>
      </View>
    );
  }

  // Mobile: Ánh sáng ngọc thảo mộc thanh thoát ở phần đầu, tiếp nối dịu dàng vào nền kem
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none" aria-hidden>
      <Svg width="100%" height="100%" style={StyleSheet.absoluteFill}>
        <Defs>
          <LinearGradient id="bgMobileTop" x1="20%" y1="0%" x2="80%" y2="60%">
            <Stop offset="0%" stopColor="#D5EADB" stopOpacity="0.9" />
            <Stop offset="35%" stopColor="#E4F3E9" stopOpacity="0.6" />
            <Stop offset="70%" stopColor="#F1F7F3" stopOpacity="0.3" />
            <Stop offset="100%" stopColor="#F8F9F6" stopOpacity="0" />
          </LinearGradient>

          <LinearGradient id="bgMobileBottom" x1="50%" y1="100%" x2="50%" y2="70%">
            <Stop offset="0%" stopColor="#F7EFE8" stopOpacity="0.5" />
            <Stop offset="100%" stopColor="#F8F9F6" stopOpacity="0" />
          </LinearGradient>
        </Defs>
        <Rect width="100%" height="100%" fill="#F8F9F6" />
        <Rect width="100%" height="100%" fill="url(#bgMobileTop)" />
        <Rect width="100%" height="100%" fill="url(#bgMobileBottom)" />
      </Svg>
    </View>
  );
}

// ─── AuthScreen ───────────────────────────────────────────────────────────────
export function AuthScreen({ title, subtitle, notice, error, footer, children }: AuthScreenProps) {
  const { width } = useWindowDimensions();
  const isDesktop = width >= DESKTOP_MIN;

  return (
    <SafeAreaView edges={['top', 'bottom']} style={st.safeArea}>
      <AuthBackground isDesktop={isDesktop} />

      {isDesktop ? (
        <ScrollView
          contentContainerStyle={st.desktopScroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={st.desktopRow}>
            {/* Cột trái: Giới thiệu tinh gọn */}
            <View style={st.introCol}>
              <View style={st.badgePill}>
                <Sparkles size={13} color={colors.primary} strokeWidth={iconStroke} />
                <Text style={st.badgeText}>Trợ lý ẩm thực AI</Text>
              </View>

              <Text style={st.introHeading}>{'Nấu ngon chuẩn vị\ntừ nguyên liệu sẵn có'}</Text>

              <Text style={st.introBody}>
                Tận dụng thực phẩm trong tủ lạnh, tối ưu dinh dưỡng mỗi ngày.
              </Text>

              <View style={st.bentoGrid}>
                <FeatureCard
                  icon={Camera}
                  title="Nhận diện nguyên liệu"
                  desc="Quét ảnh tủ lạnh, phân loại tức thì"
                />
                <FeatureCard
                  icon={ChefHat}
                  title="Gợi ý món ăn thông minh"
                  desc="Hàng ngàn công thức chuẩn vị sẵn có"
                />
                <FeatureCard
                  icon={UtensilsCrossed}
                  title="Kiểm soát dinh dưỡng"
                  desc="Cân đối calo & cảnh báo dị ứng"
                />
              </View>
            </View>

            {/* Cột phải: Card form xác thực */}
            <View style={st.formCol}>
              <FormCard title={title} subtitle={subtitle} notice={notice} error={error} footer={footer}>
                {children}
              </FormCard>
            </View>
          </View>
        </ScrollView>
      ) : (
        <ScrollView
          contentContainerStyle={st.mobileScroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Header Mobile thanh lịch */}
          <View style={st.mobileHero}>
            <BrandMark style={{ marginBottom: 10 }} />
            <Text style={st.mobileTagline}>Trợ lý nấu ăn thông minh từ nguyên liệu bạn có</Text>
          </View>

          {/* Form Card */}
          <View style={st.mobileFormWrap}>
            <FormCard title={title} subtitle={subtitle} notice={notice} error={error} footer={footer}>
              {children}
            </FormCard>
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function FormCard({
  title,
  subtitle,
  notice,
  error,
  footer,
  children,
}: Omit<AuthScreenProps, 'title' | 'subtitle'> & { title: string; subtitle: string }) {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(8)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 220,
        useNativeDriver: Platform.OS !== 'web',
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 220,
        useNativeDriver: Platform.OS !== 'web',
      }),
    ]).start();
  }, []);

  return (
    <Animated.View style={{ opacity: fadeAnim, transform: [{ translateY: slideAnim }], width: '100%' }}>
      <Card style={st.card}>
        <View style={st.cardBrandHeader}>
          <BrandMark />
        </View>

        <View style={st.header}>
          <Txt v="title" style={st.title}>{title}</Txt>
          <Txt v="body" style={st.subtitle}>{subtitle}</Txt>
        </View>

        {!!notice && <SafetyBadge>{notice}</SafetyBadge>}
        {!!error && <SafetyBadge tone="warn">{error}</SafetyBadge>}

        <View style={st.form}>{children}</View>

        {footer && <View style={st.footer}>{footer}</View>}
      </Card>
    </Animated.View>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  desc,
}: {
  icon: typeof Camera;
  title: string;
  desc: string;
}) {
  return (
    <View style={st.featureCard}>
      <View style={st.featureIconWrap}>
        <Icon size={16} color={colors.primary} strokeWidth={iconStroke} />
      </View>
      <View style={st.featureContent}>
        <Text style={st.featureTitle}>{title}</Text>
        <Text style={st.featureDesc}>{desc}</Text>
      </View>
    </View>
  );
}

// Luật mật khẩu hiện trực tiếp khi gõ (cùng luật backend) — biết thiếu gì trước khi bấm.
export function PasswordChecklist({ password }: { password: string }) {
  const rules = passwordRules(password);
  const allOk = password.length > 0 && rules.every((r) => r.ok) && !isPasswordTooLong(password);
  return (
    <View
      style={[st.rulesCard, allOk && { backgroundColor: colors.primarySoft, borderColor: colors.primaryLine }]}
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

// ─── Styles ───────────────────────────────────────────────────────────────────
const st = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.bg,
  },

  // Desktop Layout
  desktopScroll: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 54,
    paddingVertical: 36,
  },
  desktopRow: {
    width: '100%',
    maxWidth: 1140,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 64,
  },
  introCol: {
    flex: 1,
    maxWidth: 480,
  },
  badgePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    backgroundColor: colors.primarySoft,
    paddingVertical: 4,
    paddingHorizontal: 11,
    borderRadius: radius.full,
    marginBottom: 14,
  },
  badgeText: {
    fontFamily: fonts.semibold,
    fontSize: 12,
    color: colors.primaryDark,
  },
  introHeading: {
    fontFamily: fonts.display,
    fontSize: 32,
    lineHeight: 38,
    color: colors.ink,
    letterSpacing: -0.4,
    marginBottom: 8,
  },
  introBody: {
    fontFamily: fonts.medium,
    fontSize: 14,
    lineHeight: 20,
    color: colors.muted,
    marginBottom: 18,
  },

  // Bento Features (Compact, Transparent & Borderless)
  bentoGrid: {
    gap: 10,
  },
  featureCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: 'transparent',
    paddingVertical: 6,
    paddingHorizontal: 4,
  },
  featureIconWrap: {
    width: 32,
    height: 32,
    borderRadius: 9,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  featureContent: {
    flex: 1,
    gap: 1,
  },
  featureTitle: {
    fontFamily: fonts.bold,
    fontSize: 13,
    color: colors.ink,
  },
  featureDesc: {
    fontFamily: fonts.medium,
    fontSize: 12,
    lineHeight: 16,
    color: colors.muted,
  },

  formCol: {
    width: 440,
    maxWidth: '100%',
  },

  // Mobile Layout
  mobileScroll: {
    flexGrow: 1,
    paddingVertical: 20,
    paddingHorizontal: 20,
  },
  mobileHero: {
    alignItems: 'center',
    paddingTop: 12,
    paddingBottom: 22,
  },
  mobileTagline: {
    fontFamily: fonts.medium,
    fontSize: 13,
    lineHeight: 18,
    color: colors.muted,
    textAlign: 'center',
  },
  mobileFormWrap: {
    width: '100%',
    maxWidth: 440,
    alignSelf: 'center',
  },

  // Form Card
  card: {
    gap: 18,
    padding: 28,
    borderRadius: 24,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderSoft,
    boxShadow: '0 16px 40px rgba(26, 33, 28, 0.06)',
    elevation: 4,
  },
  cardBrandHeader: {
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

  // Password Checklist
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
  rule: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  ruleText: {
    fontFamily: fonts.medium,
    fontSize: 12,
    color: colors.muted,
  },
});
