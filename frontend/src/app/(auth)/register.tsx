import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import { AuthScreen, PasswordChecklist } from '../../components/AuthScreen';
import { EmailField, TextField } from '../../components/TextField';
import { Button, LinkText } from '../../components/ui';
import { registerAccount } from '../../lib/auth';
import { isStrongPassword, isValidEmail } from '../../lib/password';
import { useSubmit } from '../../lib/useSubmit';

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
      subtitle="Cần xác minh email trước khi đăng nhập."
      notice={notice}
      error={error}
      footer={
        <View style={{ gap: 12, alignItems: 'center' }}>
          <Button style={{ alignSelf: 'stretch' }} label={busy ? 'Đang tạo…' : 'Tạo tài khoản'} disabled={busy || !ready} onPress={submit} />
          <LinkText label="Đã có tài khoản? Đăng nhập" onPress={() => router.replace('/login')} />
        </View>
      }
    >
      <EmailField value={email} onChangeText={setEmail} />
      <TextField label="Mật khẩu" value={password} onChangeText={setPassword} secret autoComplete="new-password" textContentType="newPassword" />
      <PasswordChecklist password={password} />
      <TextField
        label="Nhập lại mật khẩu"
        value={confirm}
        onChangeText={setConfirm}
        secret
        error={confirm && confirm !== password ? 'Hai mật khẩu chưa khớp' : null}
        autoComplete="new-password"
        onSubmitEditing={submit}
      />
    </AuthScreen>
  );
}
