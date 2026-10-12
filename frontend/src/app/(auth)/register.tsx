import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import { AuthScreen, PasswordChecklist } from '../../components/AuthScreen';
import { EmailField, TextField } from '../../components/TextField';
import { Button, LinkText, Txt } from '../../components/ui';
import { registerAccount } from '../../lib/auth';
import { isStrongPassword, isValidEmail } from '../../lib/password';
import { useSubmit } from '../../lib/useSubmit';
import { colors } from '../../theme';

export default function Register() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const { busy, error, run } = useSubmit('Đăng ký thất bại');
  const ready = isValidEmail(email) && isStrongPassword(password) && confirm === password;

  // Backend + Supabase kiểm lại luật mật khẩu và HIBP — client chỉ báo sớm
  const submit = () =>
    ready &&
    run(async () => {
      setNotice(await registerAccount(email.trim(), password));
      setPassword('');
      setConfirm('');
    });

  return (
    <AuthScreen
      title="Tạo tài khoản"
      subtitle="Đăng ký tài khoản để lưu công thức và cá nhân hóa thực đơn."
      notice={notice}
      error={error}
      footer={
        <View style={{ gap: 14, alignItems: 'center', width: '100%' }}>
          <Button style={{ alignSelf: 'stretch' }} label={busy ? 'Đang tạo tài khoản…' : 'Tạo tài khoản'} disabled={busy || !ready} onPress={submit} />
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Txt v="body" style={{ color: colors.muted, fontSize: 13 }}>Đã có tài khoản?</Txt>
            <LinkText label="Đăng nhập" onPress={() => router.replace('/login')} />
          </View>
        </View>
      }
    >
      <EmailField value={email} onChangeText={setEmail} />
      <TextField
        label="Mật khẩu"
        placeholder="Tối thiểu 8 ký tự"
        value={password}
        onChangeText={setPassword}
        secret
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <PasswordChecklist password={password} />
      <TextField
        label="Nhập lại mật khẩu"
        placeholder="Nhập lại chính xác mật khẩu"
        value={confirm}
        onChangeText={setConfirm}
        secret
        error={confirm && confirm !== password ? 'Hai mật khẩu chưa khớp' : null}
        autoComplete="new-password"
        textContentType="newPassword"
        onSubmitEditing={submit}
        returnKeyType="go"
      />
    </AuthScreen>
  );
}
