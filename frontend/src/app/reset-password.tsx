import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import { AuthScreen, PasswordChecklist } from '../components/AuthScreen';
import { TextField } from '../components/TextField';
import { Button, LinkText } from '../components/ui';
import { resetPassword } from '../lib/auth';
import { isStrongPassword } from '../lib/password';
import { IS_WEB } from '../lib/sessionStore';
import { useSubmit } from '../lib/useSubmit';

type RecoveryLink = { token: string | null; problem: string | null };

const INVALID_LINK = 'Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn — gửi lại yêu cầu mới.';

// Link trong email: /reset-password#access_token=…&type=recovery (lỗi: #error_code=otp_expired…).
// Đọc 1 lần rồi xoá phần # khỏi URL để token không nằm lại trong lịch sử trình duyệt.
function readRecoveryLink(): RecoveryLink {
  if (!IS_WEB || typeof window === 'undefined') return { token: null, problem: 'Mở link đặt lại mật khẩu trong trình duyệt.' };
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  window.history.replaceState(null, '', window.location.pathname);
  const token = params.get('type') === 'recovery' ? params.get('access_token') : null;
  return token ? { token, problem: null } : { token: null, problem: INVALID_LINK };
}

export default function ResetPassword() {
  const [link] = useState(readRecoveryLink);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const { busy, error, run } = useSubmit('Chưa đổi được mật khẩu');
  const ready = !!link.token && !notice && isStrongPassword(password) && confirm === password;

  const submit = () => ready && run(async () => setNotice(await resetPassword(link.token!, password)));

  return (
    <AuthScreen
      title="Đặt mật khẩu mới"
      subtitle="Mật khẩu mới cần đủ các yêu cầu bên dưới."
      notice={notice}
      error={error ?? link.problem}
      footer={
        <View style={{ gap: 12, alignItems: 'center' }}>
          <Button style={{ alignSelf: 'stretch' }} label={busy ? 'Đang lưu…' : 'Lưu mật khẩu mới'} disabled={busy || !ready} onPress={submit} />
          <LinkText label="Về trang đăng nhập" onPress={() => router.replace('/login')} />
        </View>
      }
    >
      <TextField label="Mật khẩu mới" value={password} onChangeText={setPassword} secret autoComplete="new-password" textContentType="newPassword" />
      <PasswordChecklist password={password} />
      <TextField
        label="Nhập lại mật khẩu mới"
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
