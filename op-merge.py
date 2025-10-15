import os
import sys
import glob
import uuid
import ffmpeg
import shutil
import hashlib
import subprocess
from pathlib import Path

# =========================
# CẤU HÌNH MẶC ĐỊNH
# =========================
BASE_PATH = r"D:/Second-Jobs/tho_video"
SOURCE_FOLDER = os.path.join(BASE_PATH, "1_SOURCE")
base_out = r"D:/3M-system/Content-System"
CACHE_DIR = Path(r"D:\Dream life\3M-system\Cache")  # Bộ nhớ đệm toàn cục

MIN_DURATION_CLIP = 3
MAX_DURATION_CLIP = 20
MAX_DURATION_FINAL_VIDEO = 500

TARGET_FPS = 30
AUDIO_RATE = 48000
AUDIO_CH = 2
QP_VALUE = "18"

# =========================
# TIỆN ÍCH CHUNG
# =========================
def fix_encoding():
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

def run_quiet(cmd, check=True):
    return subprocess.run(cmd, check=check, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def gpu_available():
    try:
        encoders = subprocess.check_output(
            ["ffmpeg", "-hide_banner", "-encoders"], stderr=subprocess.STDOUT
        ).decode("utf-8", errors="ignore").lower()
        return "h264_nvenc" in encoders
    except Exception:
        return False

def encode_params_high_quality(use_gpu: bool):
    common = [
        "-r", str(TARGET_FPS),
        "-vsync", "cfr",
        "-g", str(TARGET_FPS * 2),
        "-bf", "3",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-c:a", "aac", "-b:a", "192k",
        "-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CH),
        "-af", "aresample=async=1:first_pts=0",
        "-fflags", "+genpts",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        "-reset_timestamps", "1",
    ]
    if use_gpu:
        return [
            "-c:v", "h264_nvenc",
            "-preset", "p7",
            "-rc", "constqp", "-qp", QP_VALUE,
        ] + common
    else:
        return [
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
        ] + common

def check_input_videos(input_folder: str):
    vids = []
    for ext in (".mp4", ".mov", ".mkv", ".avi", ".flv"):
        vids.extend(glob.glob(os.path.join(input_folder, f"*{ext}")))
    return sorted(vids)

def get_duration(path: str) -> float:
    try:
        return float(ffmpeg.probe(path)["format"]["duration"])
    except Exception:
        return 0.0

def video_hash(path: str, sample_bytes: int = 2_000_000) -> str:
    """Tạo hash duy nhất dựa trên nội dung video (đọc 2MB đầu)."""
    try:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            h.update(f.read(sample_bytes))
        return h.hexdigest()[:12]
    except Exception:
        return uuid.uuid4().hex[:12]

# =========================
# XỬ LÝ CHÍNH (CÓ CACHE)
# =========================
def transcode_to_fixed(inputs, temp_dir: Path, use_gpu: bool):
    """
    Chuẩn hoá clip với bộ nhớ đệm toàn cục dựa trên hash nội dung.
    Mỗi clip chỉ encode 1 lần duy nhất, dùng lại nếu trùng hash.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    enc = encode_params_high_quality(use_gpu)
    fixed = []

    for src in inputs:
        src_path = Path(src)
        vid_hash = video_hash(str(src_path))
        cache_file = CACHE_DIR / f"{vid_hash}_fixed.mp4"
        meta_file = CACHE_DIR / f"{vid_hash}.info"
        fixed_path = temp_dir / f"fixed_{vid_hash}.mp4"

        # ⚡ Nếu có cache, dùng lại
        if cache_file.exists():
            dur = get_duration(str(cache_file))
            if MIN_DURATION_CLIP < dur <= MAX_DURATION_CLIP:
                shutil.copy2(cache_file, fixed_path)
                fixed.append((str(fixed_path), dur))
                print(f"✅ Dùng lại cache: {src_path.name} ({dur:.2f}s)")
                continue

        # 🔧 Nếu chưa có cache, encode mới
        print(f"⚙️ Mã hoá mới: {src_path.name}")
        if use_gpu:
            cmd = ["ffmpeg", "-y", "-hwaccel", "cuda", "-i", str(src_path)] + enc + [str(fixed_path)]
        else:
            cmd = ["ffmpeg", "-y", "-i", str(src_path)] + enc + [str(fixed_path)]

        try:
            run_quiet(cmd, check=True)
        except subprocess.CalledProcessError:
            print("⚠️ Lỗi FFmpeg, hiển thị log chi tiết:")
            subprocess.run(cmd)

        dur = get_duration(str(fixed_path))
        if dur <= MIN_DURATION_CLIP or dur > MAX_DURATION_CLIP:
            print(f"⏩ Bỏ clip ({dur:.2f}s): {src_path.name}")
            try: fixed_path.unlink(missing_ok=True)
            except: pass
            continue

        # 💾 Lưu cache
        shutil.copy2(fixed_path, cache_file)
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write(f"name={src_path.name}\nsize={src_path.stat().st_size}\nhash={vid_hash}\n")

        fixed.append((str(fixed_path), dur))
        print(f"✅ Fixed: {src_path.name} ({dur:.2f}s) → Lưu cache {cache_file.name}")

    return fixed

def concat_batch(batch_files, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = out_path.parent / f"__list_{uuid.uuid4().hex}.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in batch_files:
            f.write(f"file '{os.path.abspath(p)}'\n")

    try:
        run_quiet([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            "-fflags", "+genpts",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            str(out_path)
        ], check=True)
    finally:
        try: list_file.unlink(missing_ok=True)
        except: pass

def merge_many_videos_by_duration(input_files, out_root: Path, target_duration: float):
    out_root.mkdir(parents=True, exist_ok=True)
    temp_dir = out_root / "__temp_merge"
    used_gpu = gpu_available()
    print(f"🖥️ GPU NVENC: {'ON' if used_gpu else 'OFF (CPU fallback)'}")

    fixed = transcode_to_fixed(input_files, temp_dir, used_gpu)
    if not fixed:
        print("❌ Không có clip hợp lệ sau khi chuẩn hoá.")
        return 0

    outputs, idx, total_clips = 0, 0, len(fixed)

    while idx < total_clips:
        batch, total = [], 0.0
        while idx < total_clips and total < target_duration:
            path_i, dur_i = fixed[idx]
            if total + dur_i >= MAX_DURATION_FINAL_VIDEO:
                print(f"⏩ Bỏ clip {Path(path_i).name} vì vượt {MAX_DURATION_FINAL_VIDEO:.1f}s.")
                break
            batch.append(path_i)
            total += dur_i
            idx += 1

        if not batch:
            break

        outputs += 1
        out_path = out_root / f"final_{outputs:03d}.mp4"
        print(f"🎬 Render #{outputs}: {len(batch)} clips ~ {total:.2f}s → {out_path.name}")
        concat_batch(batch, out_path)

    # ❌ Không xoá temp_dir → giữ cache tạm cho lần sau
    return outputs

# =========================
# LUỒNG TƯƠNG TÁC
# =========================
def process_videos():
    fix_encoding()

    topic = input("📁 Nhập topic nguồn (vd: lookalikecam-0): ").strip()

    print(
        "📂 Chọn thư mục nguồn cần xử lý:\n"
        "1) LONGS\n"
        "2) SHORTS\n"
        "3) KHÁC (tự nhập đường dẫn đầy đủ)"
    )
    choice = input("👉 Nhập (1/2/3): ").strip()

    if choice == "1":
        source_folder = Path(SOURCE_FOLDER) / topic / "LONGS"
    elif choice == "2":
        source_folder = Path(SOURCE_FOLDER) / topic / "SHORTS"
    elif choice == "3":
        custom_path = input("🔎 Dán đường dẫn thư mục nguồn: ").strip().strip('"').strip("'")
        source_folder = Path(custom_path)
        if not source_folder.is_dir():
            print(f"❌ Đường dẫn không tồn tại hoặc không phải thư mục: {custom_path}")
            return
    else:
        print("❌ Lựa chọn không hợp lệ.")
        return

    s = input("⏱️ Nhập duration mỗi video (s) [mặc định 40]: ").strip()
    target_duration = float(s) if s else 40.0

    sub_out = input("🔹 Nhập topic output (vd: Lookalikecam): ").strip() or "Output"
    output_root = Path(base_out) / sub_out
    output_root.mkdir(parents=True, exist_ok=True)

    videos = check_input_videos(str(source_folder))
    if not videos:
        print("❌ Không tìm thấy video hợp lệ.")
        return

    count = merge_many_videos_by_duration(videos, output_root, target_duration)

    if count > 0:
        print(f"✅ Hoàn tất. Đã xuất {count} video tại: {output_root}")
    else:
        print("❌ Không xuất được video nào.")

if __name__ == "__main__":
    process_videos()
