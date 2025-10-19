import os, re, random, subprocess, sys, uuid
from pathlib import Path
from tkinter import Tk, filedialog, simpledialog, messagebox

# =========================
# ⚙️ CẤU HÌNH
# =========================
SCENE_THRESHOLD = 0.30
MIN_DURATION = 2.0
ENCODE_PRESET = "p7"
QP_VALUE = 18
TARGET_FPS = 30
AUDIO_RATE = 48000
AUDIO_CH = 2
FAST_MODE = int(os.getenv("FAST_MODE", "0"))
FAST_FPS = 12
PROBESIZE = "100M"
ANALYZE_DUR = "10M"

# =========================
# GUI INPUT
# =========================
def gui_select_folder(prompt: str, initial: str = ".") -> str:
    Tk().withdraw()
    folder = filedialog.askdirectory(title=prompt, initialdir=initial)
    return folder

def gui_input_text(prompt: str, default: str = "") -> str:
    Tk().withdraw()
    return simpledialog.askstring("Input", prompt, initialvalue=default) or default

def get_inputs_from_gui():
    topic_path = gui_select_folder("📁 Chọn thư mục topic để tách clips")
    if not topic_path:
        messagebox.showerror("Lỗi", "Bạn chưa chọn thư mục topic để tách.")
        sys.exit(1)
    topic = Path(topic_path).name
    base_folder = Path(topic_path)

    output_subfolder = gui_input_text("📂 Nhập tên thư mục xuất trong DEMO-CAPCUT để tách:", "Hook")
    output_folder = base_folder / "DEMO-CAPCUT" / output_subfolder
    output_folder.mkdir(parents=True, exist_ok=True)

    source_folders = []
    while True:
        src = gui_select_folder("🎬 Chọn thư mục nguồn video để tách (có thể lặp lại)")
        if not src or not Path(src).is_dir():
            break
        source_folders.append(src)
        more = simpledialog.askstring("Thêm?", "Chọn thêm thư mục để tách? (y/n)").strip().lower()
        if more != "y":
            break

    shuffle = simpledialog.askstring("🔀 Xáo trộn?", "Xáo trộn sau khi tách? (y/n)", initialvalue="n").strip().lower() == "y"

    speed_input = gui_input_text("⏩ Nhập khoảng speed sau khi tách (VD: 1.0-1.2):", "1.0-1.0")
    speed_range = (1.0, 1.0)
    if speed_input:
        try:
            speed_range = tuple(map(float, speed_input.split("-")))
        except: pass

    return topic, base_folder, output_folder, source_folders, shuffle, speed_range

# =========================
# TIỆN ÍCH VIDEO
# =========================
def run(cmd, quiet=True, check=True, stderr_to=None):
    if quiet:
        err = open(stderr_to, "w", encoding="utf-8") if stderr_to else subprocess.DEVNULL
        try:
            return subprocess.run(cmd, check=check, stdout=subprocess.DEVNULL, stderr=err)
        finally:
            if stderr_to: err.close()
    else:
        return subprocess.run(cmd, check=check)

def _has(kind: str, name: str) -> bool:
    try:
        out = subprocess.check_output(["ffmpeg","-hide_banner", f"-{kind}s"], stderr=subprocess.STDOUT)
        return name.lower() in out.decode("utf-8","ignore").lower()
    except: return False

def pick_hwaccel_and_dec(input_path: str):
    codec = "unknown"
    try:
        codec = subprocess.check_output([
            "ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_name",
            "-of","default=nokey=1:noprint_wrappers=1", input_path
        ], stderr=subprocess.STDOUT, text=True).strip().lower()
    except: pass

    hwaccel_args, vdec_override, using_cuda = [], [], False
    has_nvenc = _has("encoder", "h264_nvenc")

    if codec in ("h264","hevc","h265"):
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
    except: return 0.0

def detect_scenes_ffmpeg(input_path: str, thr: float, min_duration: float) -> list[tuple[float,float]]:
    log_file = Path(input_path).with_suffix(".scene.log")
    hwaccel_args, vdec_override, using_cuda = pick_hwaccel_and_dec(input_path)
    vf_parts = ["select='gt(scene,%.2f)'" % thr, "showinfo"]
    vf = ",".join(vf_parts)
    cmd = (["ffmpeg","-hide_banner","-an","-probesize", PROBESIZE, "-analyzeduration", ANALYZE_DUR] +
           hwaccel_args + vdec_override +
           ["-i", input_path, "-filter:v", vf, "-f","null","-"])
    with open(log_file, "w", encoding="utf-8") as errf:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=errf)

    times = [0.0]
    rgx = re.compile(r"pts_time:(\\d+\\.\\d+)")
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
    except: pass
    return spans

def cut_one_pass(input_path: str, start: float, end: float, out_path: str, speed: float = 1.0):
    hwaccel_args, vdec_override, using_cuda = pick_hwaccel_and_dec(input_path)
    vpre = "hwdownload,format=nv12," if using_cuda else ""
    vf = f"{vpre}setpts=PTS/{speed}"
    af = f"{atempo_chain(speed)},aresample=async=1:first_pts=0"
    vcodec = ["-c:v","h264_nvenc","-preset",ENCODE_PRESET,"-rc","constqp","-qp",str(QP_VALUE),
              "-profile:v","high","-pix_fmt","yuv420p","-bf","3"] if _has("encoder", "h264_nvenc") \
             else ["-c:v","libx264","-preset","slow","-crf","18","-pix_fmt","yuv420p","-bf","3"]
    err_log = Path(out_path).with_suffix(".err.txt")
    cmd = (["ffmpeg","-y","-hide_banner","-probesize", PROBESIZE, "-analyzeduration", ANALYZE_DUR] +
           hwaccel_args + ["-ss", f"{start:.3f}", "-to", f"{end:.3f}"] +
           vdec_override + ["-i", input_path,
           "-filter_complex", f"[0:v]{vf}[v];[0:a]{af}[a]",
           "-map","[v]","-map","[a]"] + vcodec +
           ["-r", str(TARGET_FPS), "-fps_mode","cfr", "-g", str(TARGET_FPS*2),
            "-c:a","aac","-b:a","192k","-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CH),
            "-fflags","+genpts","-avoid_negative_ts","make_zero","-reset_timestamps","1",
            "-movflags","+faststart", str(out_path)])
    run(cmd, quiet=True, check=True, stderr_to=str(err_log))
    try: err_log.unlink(missing_ok=True)
    except: pass

# =========================
# MAIN
# =========================
def main():
    topic, base_folder, output_folder, source_dirs, DO_SHUFFLE, SPEED_RANGE = get_inputs_from_gui()
    temp_dir = base_folder / "_TEMP_GPU_SPLIT"
    temp_dir.mkdir(parents=True, exist_ok=True)
    total_videos = total_scenes = total_valid = 0
    print(f"🖥️ NVENC encode: {'ON' if _has('encoder','h264_nvenc') else 'OFF'} | FAST_MODE={FAST_MODE}")

    for folder in source_dirs:
        video_files = [f for f in os.listdir(folder) if f.lower().endswith((".mp4",".mov",".mkv",".avi",".flv"))]
        total_videos += len(video_files)

        for video in video_files:
            input_path = Path(folder) / video
            name = input_path.stem
            safe_name = re.sub(r'[\\\\/:*?\"<>|]', '_', name)

            print(f"🔎 Dò cảnh → {video}")
            spans = detect_scenes_ffmpeg(str(input_path), SCENE_THRESHOLD, MIN_DURATION)
            total_scenes += len(spans)
            if not spans: continue

            for i, (st, en) in enumerate(spans, start=1):
                speed = round(random.uniform(*SPEED_RANGE), 3)
                out_name = f"{safe_name}_S{i:02d}_x{speed}.mp4"
                out_path = temp_dir / out_name
                cut_one_pass(str(input_path), st, en, out_path, speed)
                dur = probe_duration(str(out_path))
                if dur >= MIN_DURATION:
                    final_path = output_folder / out_path.name
                    os.replace(out_path, final_path)
                    total_valid += 1
                else:
                    out_path.unlink(missing_ok=True)

    print(f"\n✅ Tổng video: {total_videos} | Cảnh: {total_scenes} | Hợp lệ: {total_valid}")
    print(f"📂 Xuất: {output_folder}")

if __name__ == "__main__":
    main()
