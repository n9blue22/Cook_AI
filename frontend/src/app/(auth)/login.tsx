import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import { AuthScreen } from '../../components/AuthScreen';
import { EmailField, TextField } from '../../components/TextField';
import { Button, LinkText, Txt } from '../../components/ui';
import { useAuth } from '../../lib/auth';
import { isValidEmail } from '../../lib/password';
import { useSubmit } from '../../lib/useSubmit';
import { colors } from '../../theme';

export default function Login() {
  const { verified } = useLocalSearchParams<{ verified?: string }>(); // link xác minh email trỏ về /login?verified=1
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { busy, error, run } = useSubmit('Đăng nhập thất bại');
  const ready = isValidEmail(email) && password.length > 0;

  // Thành công → root layout thấy đã đăng nhập, tự chuyển sang app
  const submit = () => ready && run(() => login(email.trim(), password));

  return (
    <AuthScreen
      title="Đăng nhập"
      subtitle="Chụp nguyên liệu, nhận gợi ý món ngon chuẩn vị."
      notice={verified === '1' ? 'Email đã được xác minh — đăng nhập để bắt đầu.' : null}
      error={error}
      footer={
        <View style={{ gap: 14, alignItems: 'center', width: '100%' }}>
          <Button style={{ alignSelf: 'stretch' }} label={busy ? 'Đang đăng nhập…' : 'Đăng nhập'} disabled={busy || !ready} onPress={submit} />
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Txt v="body" style={{ color: colors.muted, fontSize: 13 }}>Chưa có tài khoản?</Txt>
            <LinkText label="Đăng ký ngay" onPress={() => router.replace('/register')} />
          </View>
        </View>
      }
    >
      <EmailField value={email} onChangeText={setEmail} />
      <TextField
        label="Mật khẩu"
        placeholder="Nhập mật khẩu của bạn"
        value={password}
        onChangeText={setPassword}
        secret
        autoComplete="current-password"
        textContentType="password"
        onSubmitEditing={submit}
        returnKeyType="go"
      />
      <View style={{ alignItems: 'flex-end', marginTop: -4 }}>
        <LinkText label="Quên mật khẩu?" onPress={() => router.replace('/forgot-password')} />
      </View>
    </AuthScreen>
  );
}
