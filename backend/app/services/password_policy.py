"""Luật mật khẩu (cùng luật với frontend lib/password.ts và cấu hình Supabase Auth) + kiểm tra rò rỉ qua HIBP.

HIBP chạy ở backend vì tính năng "leaked password protection" của Supabase chỉ có ở gói Pro — nên lớp này
bỏ qua được nếu ai đó gọi thẳng Supabase Auth. Luật độ mạnh thì Supabase tự chặn (không bỏ qua được).
"""

import hashlib
import logging
import re

import httpx

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72  # bcrypt của Supabase Auth chỉ dùng 72 byte đầu
HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/{prefix}"
HIBP_PREFIX_LENGTH = 5  # k-anonymity: chỉ gửi 5 ký tự đầu của SHA-1, không bao giờ gửi mật khẩu
HIBP_TIMEOUT_SEC = 5.0

_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[A-Z]"), "ít nhất 1 chữ hoa"),
    (re.compile(r"[a-z]"), "ít nhất 1 chữ thường"),
    (re.compile(r"\d"), "ít nhất 1 chữ số"),
    (re.compile(r"[^A-Za-z0-9]"), "ít nhất 1 ký tự đặc biệt"),
)


def password_problems(password: str) -> list[str]:
    """Danh sách yêu cầu còn thiếu (rỗng = đạt); câu tiếng Việt hiển thị thẳng cho user."""
    problems = [message for pattern, message in _RULES if not pattern.search(password)]
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.insert(0, f"tối thiểu {MIN_PASSWORD_LENGTH} ký tự")
    if len(password.encode()) > MAX_PASSWORD_LENGTH:
        problems.append(f"tối đa {MAX_PASSWORD_LENGTH} byte")
    return problems


async def is_password_pwned(password: str, http: httpx.AsyncClient) -> bool:
    """True nếu mật khẩu nằm trong danh sách rò rỉ của HIBP. HIBP lỗi → cho qua + ghi log (không chặn đăng ký)."""
    digest = hashlib.sha1(password.encode()).hexdigest().upper()  # noqa: S324 — SHA-1 là định dạng của HIBP
    prefix, suffix = digest[:HIBP_PREFIX_LENGTH], digest[HIBP_PREFIX_LENGTH:]
    try:
        response = await http.get(
            HIBP_RANGE_URL.format(prefix=prefix), headers={"Add-Padding": "true"}, timeout=HIBP_TIMEOUT_SEC,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("HIBP không phản hồi, bỏ qua kiểm tra mật khẩu rò rỉ: %s", error)
        return False
    return any(line.split(":")[0] == suffix and not line.endswith(":0") for line in response.text.splitlines())
