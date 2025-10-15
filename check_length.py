import os
import sys
import subprocess
from pathlib import Path
from multiprocessing import Pool, cpu_count

# =========================
# Cấu hình
# =========================
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".flv", ".webm", ".m4v"}

def get_duration(path: Path) -> float:
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "default=nokey=1:noprint_wrappers=1",
            str(path)
        ], stderr=subprocess.STDOUT, text=True).strip()
        return float(out)
    except Exception:
        return -1.0

def parse_duration_range(s: str):
    s = s.strip()
    parts = s.split(",")
    if len(parts) != 2:
        raise ValueError("⛔ Sai định dạng. Nhập như: 3,0 hoặc 3,20")
    min_sec = float(parts[0])
    max_sec = float(parts[1])
    if min_sec < 0 or max_sec < 0:
        raise ValueError("⛔ Duration phải >= 0")
    return min_sec, max_sec

def should_keep(duration, min_sec, max_sec):
    if duration < 0:
        return False
    if max_sec == 0:
        return duration >= min_sec
    return min_sec <= duration <= max_sec

def process_file(args):
    path, min_sec, max_sec, out_dir = args
    dur = get_duration(path)
    if should_keep(dur, min_sec, max_sec):
        target = out_dir / path.name
        try:
            path.replace(target)
            return ("keep", path.name, dur)
        except Exception as e:
            return ("error", path.name, str(e))
    else:
        try:
            path.unlink()
            return ("delete", path.name, dur)
        except Exception as e:
            return ("error", path.name, str(e))

def main():
    try:
        if sys.stdout and sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== LỌC VIDEO THEO ĐỘ DÀI — DÙNG MULTIPROCESSING ===")

    in_dir_str = input("1) Đường dẫn thư mục nguồn: ").strip().strip('"').strip("'")
    in_dir = Path(in_dir_str)
    if not in_dir.is_dir():
        print(f"❌ Không tìm thấy thư mục: {in_dir}")
        return

    out_dir_str = input("2) Thư mục xuất (bỏ trống = ./filter): ").strip().strip('"').strip("'")
    out_dir = Path(out_dir_str) if out_dir_str else Path.cwd() / "filter"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        range_str = input("3) Nhập duration (vd: 3,0 hoặc 3,20): ")
        min_sec, max_sec = parse_duration_range(range_str)
    except Exception as e:
        print(f"❌ {e}")
        return

    video_files = [p for p in in_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    print(f"🔍 Đang quét {len(video_files)} file…")

    # Chuẩn bị args
    args = [(p, min_sec, max_sec, out_dir) for p in video_files]

    keep_count = delete_count = err_count = 0

    with Pool(processes=min(cpu_count(), 8)) as pool:
        results = pool.map(process_file, args)

    for status, name, info in results:
        if status == "keep":
            print(f"✔ KEEP   {name}  ({info:.2f}s)")
            keep_count += 1
        elif status == "delete":
            print(f"✖ DELETE {name}  ({info:.2f}s)")
            delete_count += 1
        else:
            print(f"⚠️ ERROR  {name}: {info}")
            err_count += 1

    print("\n===== BÁO CÁO =====")
    print(f"• Tổng file quét: {len(video_files)}")
    print(f"• Giữ (di chuyển): {keep_count}")
    print(f"• Xóa: {delete_count}")
    print(f"• Lỗi xử lý: {err_count}")
    print(f"• Lưu tại: {out_dir}")

if __name__ == "__main__":
    main()
