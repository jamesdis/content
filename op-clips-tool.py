import os, re, random, subprocess, sys, time, uuid
from pathlib import Path

# =========================
# ⚙️ CẤU HÌNH
# =========================
SCENE_THRESHOLD = 0.30       # 0.30–0.60 tuùy nguồn
MIN_DURATION    = 2.0        # chỉ giữ scene >= 4s
ENCODE_PRESET   = "p7"       # p7/p6/slow (tuùy driver)
QP_VALUE        = 18         # 16 nét hơn nhưng file to hơn
TARGET_FPS      = 30
AUDIO_RATE      = 48000
AUDIO_CH        = 2

# Tăng tốc dò cảnh
FAST_MODE       = int(os.getenv("FAST_MODE", "0"))  # 0: chuẩn, 1: nhanh hơn
FAST_FPS        = 12
PROBESIZE       = "100M"
ANALYZE_DUR     = "10M"

# =========================
# TIỆN ÍCH
# =========================
def run(cmd, quiet=True, check=True, stderr_to=None):
    if quiet:
        err = open(stderr_to, "w", encoding="utf-8") if stderr_to else subprocess.DEVNULL
        try:
            return subprocess.run(cmd, check=check, stdout=subprocess.DEVNULL, stderr=err)
        finally:
            if stderr_to:
                err.close()
    else:
        return subprocess.run(cmd, check=check)

def _has(kind: str, name: str) -> bool:
    try:
        out = subprocess.check_output(["ffmpeg","-hide_banner", f"-{kind}s"], stderr=subprocess.STDOUT)
        return name.lower() in out.decode("utf-8","ignore").lower()
    except Exception:
        return False

def pick_hwaccel_and_dec(input_path: str):
    codec = "unknown"
    try:
        codec = subprocess.check_output([
            "ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_name",
            "-of","default=nokey=1:noprint_wrappers=1", input_path
        ], stderr=subprocess.STDOUT, text=True).strip().lower()
    except Exception:
        pass

    hwaccel_args, vdec_override, using_cuda = [], [], False
    has_nvenc = _has("encoder", "h264_nvenc")
    has_av1_cuvid = _has("decoder", "av1_cuvid")

    if codec in ("av1","av01"):
        if has_av1_cuvid:
            hwaccel_args = ["-hwaccel","cuda","-hwaccel_output_format","cuda","-threads","0"]
            vdec_override = ["-c:v","av1_cuvid"]
            using_cuda = True
        else:
            hwaccel_args = ["-hwaccel","d3d11va","-threads","0"]
    elif codec in ("h264","hevc","h265"):
        if has_nvenc:
            hwaccel_args = ["-hwaccel","cuda","-hwaccel_output_format","cuda","-threads","0"]
            using_cuda = True
        else:
            hwaccel_args = ["-hwaccel","d3d11va","-threads","0"]
    return hwaccel_args, vdec_override, using_cuda

def atempo_chain(speed: float) -> str:
    s = float(speed)
    chain = []
    while s > 2.0:
        chain.append("atempo=2.0"); s /= 2.0
    while s < 0.5:
        chain.append("atempo=0.5"); s /= 0.5
    chain.append(f"atempo={s:.6f}")
    return ",".join(chain)

def probe_duration(path: str) -> float:
    try:
        out = subprocess.check_output([
            "ffprobe","-v","error","-show_entries","format=duration",
            "-of","default=nokey=1:noprint_wrappers=1", path
        ], stderr=subprocess.STDOUT, text=True).strip()
        return float(out)
    except Exception:
        return 0.0

def shuffle_and_renumber_mp4(folder: str, prefix: str = "", keep_original_name: bool = True):
    p = Path(folder)
    files = [f for f in p.iterdir() if f.is_file() and f.suffix.lower() == ".mp4"]
    if not files:
        return 0
    random.shuffle(files)
    temp_map = {}
    for f in files:
        tmp = f.with_name(f.name + f".tmp_{uuid.uuid4().hex[:8]}")
        f.rename(tmp)
        temp_map[f] = tmp
    width = max(3, len(str(len(files))))
    for i, f in enumerate(files, start=1):
        tmp = temp_map[f]
        base = f.stem if keep_original_name else ""
        if keep_original_name and base:
            new_name = f"{prefix}{i:0{width}d}__{base}.mp4"
        else:
            new_name = f"{prefix}{i:0{width}d}.mp4"
        new_path = p / new_name
        tmp.rename(new_path)
    return len(files)

# =========================
# DÒ CẢNH (FFmpeg)
# =========================
def detect_scenes_ffmpeg(input_path: str, thr: float, min_duration: float) -> list[tuple[float,float]]:
    log_file = Path(input_path).with_suffix(".scene.log")
    hwaccel_args, vdec_override, using_cuda = pick_hwaccel_and_dec(input_path)
    pre_cpu = ["hwdownload","format=nv12"] if using_cuda else []
    fps_part = [f"fps={FAST_FPS}"] if FAST_MODE else []
    vf_parts = pre_cpu + fps_part + [f"select='gt(scene,{thr})'", "showinfo"]
    vf = ",".join(vf_parts)

    cmd = (["ffmpeg","-hide_banner","-an","-probesize", PROBESIZE, "-analyzeduration", ANALYZE_DUR] +
           hwaccel_args + vdec_override +
           ["-i", input_path, "-filter:v", vf, "-f","null","-"])

    with open(log_file, "w", encoding="utf-8") as errf:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=errf)

    times = [0.0]
    rgx = re.compile(r"pts_time:(\d+\.\d+)")
    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = rgx.search(line)
            if m:
                t = float(m.group(1))
                if not times or t - times[-1] > 0.15:
                    times.append(t)
    dur = probe_duration(input_path)
    if not times or (times and times[-1] < dur):
        times.append(dur)

    spans = [(a, b) for a, b in zip(times[:-1], times[1:]) if b - a >= min_duration]
    try: log_file.unlink(missing_ok=True)
    except Exception: pass
    return spans

# =========================
# CẮT CLIP + ENCODE
# =========================
def cut_one_pass(input_path: str, start: float, end: float, out_path: str, speed: float = 1.0):
    hwaccel_args, vdec_override, using_cuda = pick_hwaccel_and_dec(input_path)
    vpre = "hwdownload,format=nv12," if using_cuda else ""
    vf  = f"{vpre}setpts=PTS/{speed}"
    af  = f"{atempo_chain(speed)},aresample=async=1:first_pts=0"

    if _has("encoder", "h264_nvenc"):
        vcodec = ["-c:v","h264_nvenc","-preset",ENCODE_PRESET,"-rc","constqp","-qp",str(QP_VALUE),
                  "-profile:v","high","-pix_fmt","yuv420p","-bf","3","-spatial_aq","1","-aq-strength","8"]
    else:
        vcodec = ["-c:v","libx264","-preset","slow","-crf","18","-pix_fmt","yuv420p","-bf","3"]

    err_log = Path(out_path).with_suffix(".err.txt")

    cmd = (["ffmpeg","-y","-hide_banner","-probesize", PROBESIZE, "-analyzeduration", ANALYZE_DUR] +
           hwaccel_args + ["-ss", f"{start:.3f}", "-to", f"{end:.3f}"] +
           vdec_override + ["-i", input_path,
           "-filter_complex", f"[0:v]{vf}[v];[0:a]{af}[a]",
           "-map","[v]","-map","[a]"] + vcodec +
           ["-r", str(TARGET_FPS), "-fps_mode","cfr", "-g", str(TARGET_FPS*2),
            "-c:a","aac","-b:a","192k","-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CH),
            "-fflags","+genpts","-avoid_negative_ts","make_zero","-reset_timestamps","1",
            "-movflags","+faststart", out_path])

    run(cmd, quiet=True, check=True, stderr_to=str(err_log))
    try: err_log.unlink(missing_ok=True)
    except Exception: pass

# =========================
# MAIN
# =========================
def main():
    topic = input("📁 Nhập tên topic (VD: REUNION): ").strip()
    base_folder = os.path.join(os.getcwd(), "1_SOURCE", topic)

    print("\n📁 Chọn nơi xuất file:")
    print("1. DEMO-CAPCUT/Hook\n2. DEMO-CAPCUT/Random\n3. Nhập tên thư mục tùy chọn")
    folder_option = input("Chọn (1/2/3): ").strip()
    if folder_option == "1":
        target_subfolder = "Hook"
    elif folder_option == "2":
        target_subfolder = "Random"
    elif folder_option == "3":
        target_subfolder = input("Nhập tên thư mục đích trong DEMO-CAPCUT: ").strip()
    else:
        print("❌ Lựa chọn không hợp lệ."); return

    output_folder = os.path.join(base_folder, "DEMO-CAPCUT", target_subfolder)
    os.makedirs(output_folder, exist_ok=True)

    print("\n🎬 Chọn nguồn video:\n1. LONGS\n2. SHORTS\n3. CẢ 2")
    source_option = input("Chọn (1/2/3): ").strip()
    source_folders = []
    if source_option == "1": source_folders.append("LONGS")
    elif source_option == "2": source_folders.append("SHORTS")
    elif source_option == "3": source_folders.extend(["LONGS","SHORTS"])
    else: print("❌ Lựa chọn không hợp lệ."); return

    # Hỏi người dùng muốn shuffle không
    shuffle_choice = input("Xáo trộn vị trí các clip sau khi tách xong? (y/N): ").strip().lower()
    DO_SHUFFLE = shuffle_choice == "y"

    speed_input = input("Nhập khoảng speed (VD: 1.0-1.2, để trống = 1.0): ").strip()
    SPEED_RANGE = (1.0, 1.0)
    if speed_input:
        try: SPEED_RANGE = tuple(map(float, speed_input.split("-")))
        except Exception: pass

    temp_dir = os.path.join(base_folder, "_TEMP_GPU_SPLIT")
    os.makedirs(temp_dir, exist_ok=True)
    total_videos = total_scenes = total_valid = 0

    nvenc_on = _has("encoder", "h264_nvenc")
    print(f"\n🖥️ NVENC encode: {'ON' if nvenc_on else 'OFF (CPU fallback)'} | FAST_MODE={FAST_MODE}")

    for folder in source_folders:
        input_dir = os.path.join(base_folder, folder)
        if not os.path.isdir(input_dir): continue
        video_files = [f for f in os.listdir(input_dir) if f.lower().endswith((".mp4",".mov",".mkv",".avi",".flv"))]
        total_videos += len(video_files)

        for video in video_files:
            name = os.path.splitext(video)[0]
            safe_name = re.sub(r'[\\/:*?"<>|#@\(\)\[\]\{\}]', "_", name).strip(" .\t")
            input_path = os.path.join(input_dir, video)

            print(f"\n🔎 Dò cảnh (GPU decode nếu có) → {video}")
            spans = detect_scenes_ffmpeg(input_path, SCENE_THRESHOLD, MIN_DURATION)
            total_scenes += len(spans)
            if not spans:
                print("⚠️ Không có scene đạt MIN_DURATION."); continue

            valid = 0
            for i, (st, en) in enumerate(spans, start=1):
                speed = round(random.uniform(*SPEED_RANGE), 3)
                out_name = f"{safe_name}_S{i:02d}_x{speed}.mp4"
                out_path = os.path.join(temp_dir, out_name)
                try:
                    cut_one_pass(input_path, st, en, out_path, speed=speed)
                    dur = probe_duration(out_path)
                    if dur >= MIN_DURATION:
                        valid += 1
                        final_out = os.path.join(output_folder, os.path.basename(out_path))
                        try: os.replace(out_path, final_out)
                        except Exception: pass
                    else:
                        try: os.remove(out_path)
                        except Exception: pass
                except subprocess.CalledProcessError:
                    print(f"❌ Lỗi encode scene {i} (xem file .err.txt cạnh output)")

            total_valid += valid
            print(f"✅ {valid}/{len(spans)} scene hợp lệ (≥ {MIN_DURATION}s) cho {video}")

    try:
        for f in os.listdir(temp_dir):
            try: os.remove(os.path.join(temp_dir, f))
            except Exception: pass
        os.rmdir(temp_dir)
    except Exception: pass

    # Xáo trộn nếu được chọn
    if DO_SHUFFLE:
        count = shuffle_and_renumber_mp4(output_folder)
        if count > 0:
            print(f"🔀 Đã xáo trộn & đánh số lại {count} clip trong: {output_folder}")
        else:
            print("ℹ️ Không tìm thấy file .mp4 nào để xáo trộn.")

    print(f"\n✅📄 Tổng video: {total_videos} | Tổng cảnh: {total_scenes} | Cảnh hợp lệ (≥ {MIN_DURATION}s): {total_valid}")
    print(f"📂 Xuất tới: {output_folder}")

if __name__ == "__main__":
    try:
        if sys.stdout and sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
