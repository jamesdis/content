import os
import sys
import glob
import uuid
import ffmpeg
import shutil
import subprocess
from pathlib import Path

# =========================
# CẤU HÌNH MẶC ĐỊNH
# =========================
BASE_PATH = r"D:/Second-Jobs/tho_video"
SOURCE_FOLDER = os.path.join(BASE_PATH, "1_SOURCE")
base_out = r"D:/3M-system/Content-System"

MIN_DURATION_CLIP = 3
MAX_DURATION_CLIP = 20

MAX_DURATION_FINAL_VIDEO = 500
TARGET_FPS = 30                # Chuẩn hoá CFR
AUDIO_RATE = 48000             # 48kHz
AUDIO_CH = 2                   # Stereo
QP_VALUE = "18"                # NVENC constqp (16 = nét hơn, file to hơn)

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
    """
    Tối ưu timestamp & chất lượng để concat ổn định:
      - Video: CFR 30fps, GOP ổn định, PTS sạch
      - Audio: 48kHz stereo + aresample async chống drift
    """
    common = [
        "-r", str(TARGET_FPS),             # ép CFR
        "-vsync", "cfr",
        "-g", str(TARGET_FPS * 2),         # GOP ~2s
        "-bf", "3",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-c:a", "aac", "-b:a", "192k",
        "-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CH),
        "-af", "aresample=async=1:first_pts=0",  # chống lệch audio
        "-fflags", "+genpts",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        "-reset_timestamps", "1",
    ]
    if use_gpu:
        return [
            "-c:v", "h264_nvenc",
            "-preset", "p7",           # nếu lỗi driver -> đổi "p6"/"slow"
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

# =========================
# XỬ LÝ CHÍNH
# =========================
def transcode_to_fixed(inputs, temp_dir: Path, use_gpu: bool):
    """
    Chuẩn hoá clip → cùng codec/tham số/PTS/CFR để concat copy không lỗi.
    Trả về: [(fixed_path, duration)]
    """
    temp_dir.mkdir(parents=True, exist_ok=True)
    enc = encode_params_high_quality(use_gpu)
    fixed = []

    for i, src in enumerate(inputs):
        fixed_path = temp_dir / f"fixed_{i:04d}.mp4"
        if use_gpu:
            cmd = ["ffmpeg", "-y", "-hwaccel", "cuda", "-i", src] + enc + [str(fixed_path)]
        else:
            cmd = ["ffmpeg", "-y", "-i", src] + enc + [str(fixed_path)]

        try:
            run_quiet(cmd, check=True)
        except subprocess.CalledProcessError:
            print("⚠️ FFmpeg lỗi khi chuẩn hoá clip, chạy lại để xem log…")
            print("CMD:", " ".join(cmd))
            subprocess.run(cmd, check=True)  # in log

        dur = get_duration(str(fixed_path))
        # Giữ clip 1–60s (tuỳ bạn sửa nếu cần)
        if dur <= MIN_DURATION_CLIP or dur > MAX_DURATION_CLIP:
            print(f"⏩ Bỏ clip (duration {dur:.2f}s): {src}")
            try:
                fixed_path.unlink(missing_ok=True)
            except Exception:
                pass
            continue

        fixed.append((str(fixed_path), dur))
        print(f"✅ Fixed: {Path(src).name} ({dur:.2f}s)")
    return fixed

def concat_batch(batch_files, out_path: Path):
    """
    Concat demuxer + -c copy (nhanh/ổn định vì fixed_* đã đồng bộ).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = out_path.parent / f"__list_{uuid.uuid4().hex}.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in batch_files:
            # FFmpeg concat demuxer yêu cầu đường dẫn tuyệt đối, có quote
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
        try:
            list_file.unlink(missing_ok=True)
        except Exception:
            pass

def merge_many_videos_by_duration(input_files, out_root: Path, target_duration: float):
    """
    Ghép nhiều video liên tiếp cho đến khi hết clip.
    Mỗi video: >= target_duration và < MAX_DURATION_FINAL_VIDEO
    """
    out_root.mkdir(parents=True, exist_ok=True)
    temp_dir = out_root / "__temp_merge"
    used_gpu = gpu_available()
    print(f"🖥️ GPU NVENC: {'ON' if used_gpu else 'OFF (fallback CPU)'}")

    fixed = transcode_to_fixed(input_files, temp_dir, used_gpu)
    if not fixed:
        print("❌ Không có clip hợp lệ sau khi chuẩn hoá.")
        return 0

    outputs, idx, total_clips = 0, 0, len(fixed)

    while idx < total_clips:
        batch, total = [], 0.0
        while idx < total_clips and total < target_duration:
            path_i, dur_i = fixed[idx]
            # Không vượt 60s cho video final
            if total + dur_i >= MAX_DURATION_FINAL_VIDEO:
                print(f"⏩ Bỏ clip {Path(path_i).name} vì thêm vào sẽ {MAX_DURATION_FINAL_VIDEO:.1f} (tổng hiện tại {total:.2f}s).")
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

    # dọn rác
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass

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
        print("❌ Lựa chọn không hợp lệ. Vui lòng nhập 1/2/3.")
        return

    # Nhập duration an toàn (mặc định 40s nếu bỏ trống)
    s = input("⏱️ Nhập duration mỗi video (s) [mặc định 40]: ").strip()
    if s == "":
        target_duration = 40.0
        print("ℹ️ Dùng mặc định 40s.")
    else:
        try:
            target_duration = float(s)
            if target_duration <= 0:
                print("❌ Duration phải > 0.")
                return
        except ValueError:
            print("❌ Không phải số hợp lệ.")
            return

    print("\n📦Chọn thư mục output:")
    sub_out = input("🔹 Nhập topic output (vd: Lookalikecam): ").strip() or "Output"
    output_root = Path(base_out) / sub_out
    output_root.mkdir(parents=True, exist_ok=True)
    print(f"📁 Thư mục xuất: {output_root}")

    print(f"📁 Thư mục nguồn: {source_folder}")
    if not source_folder.is_dir():
        print("❌ Thư mục nguồn không tồn tại.")
        return

    videos = check_input_videos(str(source_folder))
    if not videos:
        print("❌ Không tìm thấy video hợp lệ trong nguồn.")
        return

    count = merge_many_videos_by_duration(videos, output_root, target_duration)

    if count > 0:
        print(f"✅ Hoàn tất. Đã xuất {count} video tại: {output_root}")
    else:
        print("❌ Không xuất được video nào.")

if __name__ == "__main__":
    process_videos()
