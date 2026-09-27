import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import { AuthScreen } from '../../components/AuthScreen';
import { EmailField } from '../../components/TextField';
import { Button, LinkText } from '../../components/ui';
import { requestPasswordReset } from '../../lib/auth';
import { isValidEmail } from '../../lib/password';
import { useSubmit } from '../../lib/useSubmit';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const { busy, error, run } = useSubmit('Chưa gửi được email');

  // Luôn cùng 1 câu trả lời — không lộ email có tồn tại hay không
  const submit = () => isValidEmail(email) && run(async () => setNotice(await requestPasswordReset(email.trim())));

  return (
    <AuthScreen
      title="Quên mật khẩu"
      subtitle="Nhập email đã đăng ký, bạn sẽ nhận link đặt lại mật khẩu."
      notice={notice}
      error={error}
      footer={
        <View style={{ gap: 12, alignItems: 'center' }}>
          <Button style={{ alignSelf: 'stretch' }} label={busy ? 'Đang gửi…' : 'Gửi link đặt lại'} disabled={busy || !isValidEmail(email)} onPress={submit} />
          <LinkText label="Quay lại đăng nhập" onPress={() => router.replace('/login')} />
        </View>
      }
    >
      <EmailField value={email} onChangeText={setEmail} onSubmitEditing={submit} />
    </AuthScreen>
  );
}
