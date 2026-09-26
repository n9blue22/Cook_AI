"""PostToolUse hook: sau mỗi lệnh có `git commit`, xoá dòng attribution khỏi commit mới nhất rồi báo lại.

Kiểm tra: git log -1 --format=%B | grep -iE "co-authored-by|generated with|claude-session|anthropic"
Có dòng khớp → amend bỏ các dòng đó, kiểm tra lại tới khi sạch (tối đa MAX_AMENDS lần).
"""

import json
import re
import subprocess
import sys

ATTRIBUTION = re.compile(r"co-authored-by|generated with|claude-session|anthropic", re.IGNORECASE)
MAX_AMENDS = 3


def git(cwd: str, *args: str, stdin: str | None = None) -> str:
    """Chạy git trong cwd, trả stdout; lỗi thì ném CalledProcessError."""
    return subprocess.run(
        ["git", *args], cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout


def attribution_lines(message: str) -> list[str]:
    """Các dòng trong commit message khớp mẫu attribution."""
    return [line for line in message.splitlines() if ATTRIBUTION.search(line)]


def report(note: str) -> None:
    """In JSON: systemMessage cho user, additionalContext để Claude báo lại."""
    print(json.dumps({
        "systemMessage": note,
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": note + " Báo cho user biết."},
    }, ensure_ascii=False))


def main() -> None:
    """Đọc payload hook, amend commit nếu cần, báo kết quả; git lỗi thì báo lỗi thay vì im lặng."""
    sys.stdin.reconfigure(encoding="utf-8")  # Windows mặc định cp1252 khi stdin/stdout là pipe
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")
    if "git commit" not in command:
        return
    try:
        strip_attribution(payload.get("cwd") or ".")
    except subprocess.CalledProcessError as error:
        report(f"Hook kiểm tra attribution LỖI khi chạy {error.cmd}: {error.stderr.strip()} — cần kiểm tra tay.")


def strip_attribution(cwd: str) -> None:
    """Amend commit mới nhất tới khi message không còn dòng attribution, báo nếu đã phải amend."""
    removed: list[str] = []
    for _ in range(MAX_AMENDS):
        message = git(cwd, "log", "-1", "--format=%B")
        found = attribution_lines(message)
        if not found:
            break
        removed += found
        clean = "\n".join(line for line in message.splitlines() if not ATTRIBUTION.search(line))
        git(cwd, "commit", "--amend", "--allow-empty", "-q", "-F", "-", stdin=clean)
    still_dirty = attribution_lines(git(cwd, "log", "-1", "--format=%B"))
    if not removed and not still_dirty:
        return
    commit = git(cwd, "log", "-1", "--format=%h").strip()
    status = f"VẪN CÒN attribution sau {MAX_AMENDS} lần amend: {still_dirty}" if still_dirty else "đã sạch"
    report(f"Hook đã amend commit {commit} để xoá {len(removed)} dòng attribution: {removed} — {status}.")


if __name__ == "__main__":
    main()
