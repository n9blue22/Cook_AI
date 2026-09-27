import { Eye, EyeOff } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, TextInputProps, View } from 'react-native';
import { isValidEmail } from '../lib/password';
import { colors, fonts, iconStroke, radius } from '../theme';

type TextFieldProps = Omit<TextInputProps, 'style' | 'secureTextEntry'> & {
  label: string;
  error?: string | null;
  secret?: boolean; // ô mật khẩu: ẩn ký tự + nút hiện/ẩn
};

// Ô nhập có nhãn; cùng kiểu ô nhập ở Confirm / Saved (cao 48, bo 16, viền border).
export function TextField({ label, error, secret, ...inputProps }: TextFieldProps) {
  const [revealed, setRevealed] = useState(false);
  const [focused, setFocused] = useState(false);
  const EyeIcon = revealed ? EyeOff : Eye;
  return (
    <View style={{ gap: 6 }}>
      <Text style={st.label}>{label}</Text>
      {/* Viền cả ô đổi màu khi đang nhập = dấu hiệu focus (thay viền đen mặc định của trình duyệt) */}
      <View style={[st.box, !!error && { borderColor: colors.warnLine }, focused && { borderColor: colors.primary }]}>
        <TextInput
          {...inputProps}
          onFocus={(event) => {
            setFocused(true);
            inputProps.onFocus?.(event);
          }}
          onBlur={(event) => {
            setFocused(false);
            inputProps.onBlur?.(event);
          }}
          accessibilityLabel={label}
          secureTextEntry={secret && !revealed}
          placeholderTextColor={colors.muted}
          style={st.input}
        />
        {secret && (
          <Pressable
            role="button"
            accessibilityLabel={revealed ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
            onPress={() => setRevealed((value) => !value)}
            hitSlop={8}
            style={st.eye}
          >
            <EyeIcon size={18} color={colors.muted} strokeWidth={iconStroke} />
          </Pressable>
        )}
      </View>
      {!!error && (
        <Text style={st.error} role="alert">
          {error}
        </Text>
      )}
    </View>
  );
}

// Ô email chuẩn cho các màn đăng nhập: bàn phím email, không viết hoa, gợi ý tự điền, báo sai định dạng.
export function EmailField(props: Pick<TextInputProps, 'value' | 'onChangeText' | 'onSubmitEditing'>) {
  const value = props.value ?? '';
  return (
    <TextField
      {...props}
      label="Email"
      error={value && !isValidEmail(value) ? 'Email chưa đúng định dạng' : null}
      keyboardType="email-address"
      autoCapitalize="none"
      autoComplete="email"
      textContentType="emailAddress"
      placeholder="ban@example.com"
    />
  );
}

const st = StyleSheet.create({
  label: { fontFamily: fonts.semibold, fontSize: 13, color: colors.ink },
  box: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 48,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  input: { flex: 1, minHeight: 46, paddingHorizontal: 14, fontFamily: fonts.medium, fontSize: 14, color: colors.ink, outlineStyle: 'solid', outlineWidth: 0 }, // web: 'auto' luôn vẽ vòng focus riêng
  eye: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  error: { fontFamily: fonts.medium, fontSize: 12, color: colors.warn },
});
