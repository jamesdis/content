import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

DEFAULT_MIN_SEC = 2
DEFAULT_MAX_SEC = 20

# ---- tiện ích cơ bản ----
def run(cmd, check=True, capture=True):
    return subprocess.run(
        cmd,
        check=check,
        stdout=(subprocess.PIPE if capture else None),
        stderr=subprocess.STDOUT,
        text=True,
    )

def detect_browser_cookies():
    """Dùng cookies của Edge/Chrome để tăng tỉ lệ lấy metadata ở TikTok (không tải)."""
    for br in ("edge", "chrome"):
        try:
            p = run(["yt-dlp", "--cookies-from-browser", br, "--dump-user-agent"], check=False)
            if p.returncode == 0:
                return ["--cookies-from-browser", br]
        except Exception:
            pass
    return []

def filter_links_by_duration(urls_file: Path, out_file: Path, min_sec: int, max_sec: int) -> dict:
    """
    Lọc link theo độ dài bằng yt-dlp (KHÔNG tải):
      - match-filter: duration >= min_sec AND duration <= max_sec
      - in: file chứa danh sách URL (mỗi dòng 1 link)
      - out: ghi ra file chỉ những link đạt điều kiện
    """
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # yt-dlp match-filter
    match_filter = f"duration >= {min_sec} and duration <= {max_sec}"

    cookie_args = detect_browser_cookies()

    cmd = [
        "yt-dlp",
        "--ignore-errors",
        "--no-warnings",
        "--no-progress",
        "--skip-download",
        "--match-filter", match_filter,
        "--print", "%(webpage_url)s",     # ✅ chỉ in link ra stdout
        "-a", str(urls_file),
    ] + cookie_args

    # Chỉ capture stdout (link), để stderr riêng
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    # Thu thập link hợp lệ
    lines = (proc.stdout or "").splitlines()
    valid = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("ERROR:")]

    # Ghi file kết quả: chỉ link
    with open(out_file, "w", encoding="utf-8") as f:
        for u in valid:
            f.write(u + "\n")

    # Đếm tổng link input
    total_input = sum(
        1 for ln in open(urls_file, "r", encoding="utf-8", errors="ignore")
        if ln.strip() and not ln.strip().startswith("#")
    )

    return {
        "total_input": total_input,
        "eligible": len(valid),
        "cookies": "Yes" if cookie_args else "No",
    }


def ask_path(prompt: str, default: str = "") -> Path:
    s = input(prompt).strip().strip('"').strip("'")
    if not s and default:
        return Path(default)
    return Path(s) if s else None

def main():
    # UTF-8 console
    try:
        if sys.stdout and sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== LỌC LINK THEO ĐỘ DÀI (YouTube + TikTok; không tải video) ===")
    links_path = input("📄 Đường dẫn file links (mỗi dòng 1 URL): ").strip().strip('"').strip("'")
    if not links_path:
        print("❌ Bạn phải nhập đường dẫn file links.")
        return
    urls_file = Path(links_path)
    if not urls_file.is_file():
        print(f"❌ Không tìm thấy file: {urls_file}")
        return

    # Nếu không nhập nơi lưu, mặc định lưu cạnh file links
    out_dir_str = input("📂 Thư mục lưu file kết quả (bỏ trống = cùng thư mục với file links): ").strip().strip('"').strip("'")
    out_dir = Path(out_dir_str) if out_dir_str else urls_file.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Tên file output
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_file = out_dir / f"filtered_links_{ts}.txt"

    # Min/Max duration
    min_s = input(f"⏱️ Min duration (giây) [mặc định {DEFAULT_MIN_SEC}]: ").strip()
    max_s = input(f"⏱️ Max duration (giây) [mặc định {DEFAULT_MAX_SEC}]: ").strip()
    try:
        min_sec = int(min_s) if min_s else DEFAULT_MIN_SEC
        max_sec = int(max_s) if max_s else DEFAULT_MAX_SEC
    except ValueError:
        print("❌ Min/Max duration phải là số nguyên (giây).")
        return
    if min_sec <= 0 or max_sec <= 0 or min_sec > max_sec:
        print("❌ Tham số duration không hợp lệ.")
        return

    print("\n🔎 Đang lọc… (không tải video)")
    stats = filter_links_by_duration(urls_file, out_file, min_sec, max_sec)

    print("\n===== BÁO CÁO =====")
    print(f"• Tổng link trong file: {stats['total_input']}")
    print(f"• Đủ điều kiện (duration {min_sec}–{max_sec}s): {stats['eligible']}")
    print(f"• Cookies từ trình duyệt: {stats['cookies']}")
    print(f"• File kết quả: {out_file}")

if __name__ == "__main__":
    main()
