// Luật mật khẩu — PHẢI giống backend app/services/password_policy.py và cấu hình Supabase Auth.
// Client kiểm tra để báo lỗi sớm; backend + Supabase kiểm lại (không tin client).

export const MIN_PASSWORD_LENGTH = 8;
const MAX_PASSWORD_BYTES = 72; // bcrypt của Supabase Auth chỉ dùng 72 byte đầu

export type PasswordRule = { label: string; ok: boolean };

export function passwordRules(password: string): PasswordRule[] {
  return [
    { label: `Tối thiểu ${MIN_PASSWORD_LENGTH} ký tự`, ok: password.length >= MIN_PASSWORD_LENGTH },
    { label: 'Ít nhất 1 chữ hoa', ok: /[A-Z]/.test(password) },
    { label: 'Ít nhất 1 chữ thường', ok: /[a-z]/.test(password) },
    { label: 'Ít nhất 1 chữ số', ok: /\d/.test(password) },
    { label: 'Ít nhất 1 ký tự đặc biệt', ok: /[^A-Za-z0-9]/.test(password) },
    { label: `Tối đa ${MAX_PASSWORD_BYTES} byte`, ok: new TextEncoder().encode(password).length <= MAX_PASSWORD_BYTES },
  ];
}

export const isStrongPassword = (password: string) => passwordRules(password).every((rule) => rule.ok);

export const isValidEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
