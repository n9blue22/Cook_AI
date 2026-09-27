"""Scanner pre-commit: bắt key thật của các dịch vụ đang dùng, bỏ qua placeholder / key công khai / dòng bị xoá.
Key giả ghép từ nhiều mảnh để chính file test này không bị scanner chặn."""

from scripts.scan_secrets import scan_diff

GROQ = "gsk_" + "A1b2C3d4" * 4
SB_SECRET = "sb_" + "secret_" + "Zx9Yw8Vu7Ts6Rq5P"
CF_TOKEN = "cfat_" + "k" * 30
GOOGLE = "AIza" + "B" * 35
USDA_KEY = "Ab12Cd34" + "Ef56Gh78Ij90Kl"
JWT = "eyJ" + "hbGciOiJIUzI1NiJ9" + ".eyJ" + "zdWIiOiJ4In0abcdef" + "." + "s" * 20


def diff_for(path: str, *added: str, removed: str = "") -> str:
    lines = [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}", f"@@ -1 +1,{len(added)} @@"]
    if removed:
        lines.append(f"-{removed}")
    return "\n".join(lines + [f"+{line}" for line in added])


def test_detects_real_looking_keys_with_file_and_line() -> None:
    diff = diff_for("backend/app/x.py", "ok = 1", f'client = Groq("{GROQ}")', f"KEY = '{SB_SECRET}'")
    findings = scan_diff(diff)

    assert [(f.path, f.line_no) for f in findings][:2] == [("backend/app/x.py", 2), ("backend/app/x.py", 3)]
    assert {f.rule for f in findings} >= {"Groq API key", "Supabase secret key"}
    assert all(GROQ not in f.excerpt and SB_SECRET not in f.excerpt for f in findings)  # không in lại cả key


def test_detects_other_providers_and_env_assignments() -> None:
    diff = diff_for("cfg.txt", f"a={GOOGLE}", f"b={JWT}", f"CF_API_TOKEN={CF_TOKEN}", f"USDA_API_KEY={USDA_KEY}")
    assert len({f.line_no for f in scan_diff(diff)}) == 4


def test_blocks_env_file_but_allows_env_example() -> None:
    assert scan_diff(diff_for("backend/.env", "ENV=development"))[0].rule.startswith("File .env")
    assert scan_diff(diff_for("backend/.env.example", "GROQ_API_KEY=xxx", "SUPABASE_SECRET_KEY=sb_secret_xxx")) == []


def test_ignores_placeholders_public_key_removed_lines_and_allow_marker() -> None:
    diff = diff_for(
        "a.py", "SUPABASE_PUBLISHABLE_KEY=sb_publishable_" + "Q" * 30, "API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxx",
        f'FAKE = "{GROQ}"  # secret-scan: allow', removed=f"old = '{GROQ}'",
    )
    assert scan_diff(diff) == []


def test_ignores_code_references_to_tokens() -> None:
    diff = diff_for(
        "auth.py", "access_token=session.access_token, expires_in=3600",
        "getAccessToken: manager.getAccessToken }", "refresh_token = new_session.refresh_token",
    )
    assert scan_diff(diff) == []
