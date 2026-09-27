import { LogOut, UserRound } from 'lucide-react-native';
import { useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { useAuth } from '../lib/auth';
import { useSubmit } from '../lib/useSubmit';
import { colors } from '../theme';
import { Button, Card, IconButton, Txt } from './ui';

// Nút "Hồ sơ cá nhân" (Main.dc.html, Desktop.dc.html). Chưa có màn hồ sơ → mở khung nhỏ: email + Đăng xuất.
export function AccountButton() {
  const { email, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const { busy, error, run } = useSubmit('Đăng xuất thất bại');

  // Thành công → root layout thấy đã đăng xuất, tự chuyển về /login
  const signOut = () => run(logout);

  return (
    <>
      <IconButton icon={UserRound} label="Hồ sơ cá nhân" onPress={() => setOpen(true)} />
      <Modal transparent visible={open} animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable accessibilityLabel="Đóng" style={st.scrim} onPress={() => setOpen(false)}>
          {/* Chặn bấm xuyên qua thẻ xuống lớp nền (lớp nền bấm = đóng) */}
          <Pressable style={st.sheet} onPress={() => {}}>
            <Card style={{ gap: 14 }}>
              <View style={{ gap: 2 }}>
                <Txt v="overline">Đang đăng nhập</Txt>
                <Txt v="bodyStrong" numberOfLines={1}>{email}</Txt>
              </View>
              {error && <Txt v="caption" style={{ color: colors.danger }}>{error}</Txt>}
              <Button kind="secondary" size="md" icon={LogOut} label={busy ? 'Đang đăng xuất…' : 'Đăng xuất'} disabled={busy} onPress={signOut} />
            </Card>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const st = StyleSheet.create({
  scrim: { flex: 1, alignItems: 'flex-end', paddingTop: 76, paddingHorizontal: 16 },
  sheet: { width: 280, maxWidth: '100%' },
});
