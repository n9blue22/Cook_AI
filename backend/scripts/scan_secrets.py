"""Quét API key / token trong phần SẮP COMMIT (git diff --cached) — chạy bởi .githooks/pre-commit.

Cài 1 lần mỗi máy clone: git config core.hooksPath .githooks
Chỉ xét dòng được THÊM. Dòng giả cố ý (test, ví dụ) đánh dấu bằng comment "secret-scan: allow".
Chỉ dùng thư viện chuẩn để chạy được bằng python hệ thống, không cần venv.
"""

import re
import subprocess
import sys
from dataclasses import dataclass

ALLOW_MARKER = "secret-scan: allow"
# Key/token cụ thể của các dịch vụ dự án đang dùng. sb_publishable_ KHÔNG nằm đây: key đó công khai (nằm trong app).
SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "Supabase secret key": re.compile(r"sb_secret_[A-Za-z0-9_-]{16,}"),
    "JWT (có thể là service_role key cũ)": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "Groq API key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "Google API key (Gemini)": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "Cloudflare API token": re.compile(r"cfat_[A-Za-z0-9_-]{20,}"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    # Gán giá trị dài cho biến tên *key/secret/token/password* (bắt cả CF_API_TOKEN=..., USDA_API_KEY=...).
    # Giá trị phải có chữ số: loại tham chiếu code như access_token=session.access_token.
    "Gán secret": re.compile(
        r"(?i)\b[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD)[A-Z0-9_]*\s*[=:]\s*['\"]?(?!x{3})"
        r"(?=[A-Za-z_\-./+]*\d)[A-Za-z0-9_\-./+]{20,}",
    ),
}
BLOCKED_FILE = re.compile(r"(^|/)\.env(\.[^/]*)?$")  # .env, .env.local... (trừ .env.example)
ALLOWED_ENV_FILES = (".env.example",)


@dataclass(frozen=True)
class Finding:
    path: str
    line_no: int
    rule: str
    excerpt: str


def scan_diff(diff: str) -> list[Finding]:
    """Tìm secret trong các dòng thêm của diff dạng `git diff -U0`."""
    findings: list[Finding] = []
    path, line_no = "", 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else line[4:]
            if BLOCKED_FILE.search(path) and not path.endswith(ALLOWED_ENV_FILES):
                findings.append(Finding(path, 0, "File .env chứa secret — không được commit", ""))
        elif line.startswith("@@"):
            line_no = int(re.search(r"\+(\d+)", line).group(1)) - 1
        elif line.startswith("+"):
            line_no += 1
            findings += _scan_line(path, line_no, line[1:])
    return findings


def _scan_line(path: str, line_no: int, text: str) -> list[Finding]:
    if ALLOW_MARKER in text:
        return []
    return [
        Finding(path, line_no, rule, _mask(match.group(0)))
        for rule, pattern in SECRET_PATTERNS.items()
        if (match := pattern.search(text))
    ]


def _mask(value: str) -> str:
    return value[:8] + "…" if len(value) > 8 else value


def main() -> int:
    """Exit 1 (chặn commit) nếu phát hiện secret."""
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # Windows mặc định cp1252 → vỡ tiếng Việt
    diff = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--no-color"], capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    findings = scan_diff(diff)
    for finding in findings:
        where = f"{finding.path}:{finding.line_no}" if finding.line_no else finding.path
        print(f"[secret-scan] {where} — {finding.rule} {finding.excerpt}", file=sys.stderr)
    if findings:
        print("[secret-scan] Commit bị chặn. Gỡ secret khỏi file (dùng biến môi trường) rồi commit lại.", file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
