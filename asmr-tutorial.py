import os
import subprocess
import tkinter as tk
from tkinter import filedialog, simpledialog
from pathlib import Path
import ffmpeg
import whisper  # 🧠 dùng để tạo caption tự động bằng AI

# =========================
# ⚙️ TIỆN ÍCH CƠ BẢN
# =========================
def get_duration(path):
    try:
        return float(ffmpeg.probe(path)["format"]["duration"])
    except Exception:
        return 0.0

def run_cmd(cmd):
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi: {e}")

def nvidia_gpu_available():
    try:
        enc = subprocess.check_output(["ffmpeg", "-hide_banner", "-encoders"],
                                      stderr=subprocess.STDOUT).decode("utf-8")
        return "h264_nvenc" in enc
    except Exception:
        return False

# =========================
# 🎧 XỬ LÝ AUDIO / VIDEO
# =========================
def change_audio_speed(input_audio, output_audio, speed):
    atempo_chain = []
    while speed > 2.0:
        atempo_chain.append("atempo=2.0")
        speed /= 2
    while speed < 0.5:
        atempo_chain.append("atempo=0.5")
        speed *= 2
    atempo_chain.append(f"atempo={speed:.3f}")
    filter_str = ",".join(atempo_chain)

    cmd = [
        "ffmpeg", "-y", "-i", input_audio,
        "-filter:a", filter_str,
        "-vn", "-c:a", "aac", "-b:a", "192k",
        output_audio
    ]
    run_cmd(cmd)

def merge_audio_video_keep_quality(video_path, audio_path, output_path):
    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "cuda",  # ưu tiên GPU NVIDIA
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",  # giữ nguyên codec gốc
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path
    ]
    run_cmd(cmd)

def merge_videos_concat_nvidia(videos, output_path):
    list_file = "__list_nvenc.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for v in videos:
            f.write(f"file '{os.path.abspath(v)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "cuda",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path
    ]
    run_cmd(cmd)
    os.remove(list_file)

def add_text_to_video(input_path, output_path, text, position="bottom"):
    pos_map = {
        "top": "y=50",
        "center": "y=(h-text_h)/2",
        "bottom": "y=h-text_h-50"
    }
    drawtext = f"drawtext=text='{text}':fontcolor=white:fontsize=36:x=(w-text_w)/2:{pos_map.get(position)}"
    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "cuda",
        "-i", input_path,
        "-vf", drawtext,
        "-c:v", "h264_nvenc", "-preset", "p7", "-cq", "18",
        "-c:a", "copy",
        output_path
    ]
    run_cmd(cmd)

# =========================
# 🧠 AI WHISPER — TẠO CAPTION TỰ ĐỘNG
# =========================
def generate_auto_caption(audio_path):
    print("🧠 Whisper đang tạo caption tự động...")
    try:
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        caption_text = result["text"].strip()
        print(f"💬 Caption: {caption_text}")
        return caption_text
    except Exception as e:
        print(f"⚠️ Whisper lỗi: {e}")
        return Path(audio_path).stem.replace("_", " ").title()

# =========================
# 📋 GIAO DIỆN NHẬP THÔNG TIN
# =========================
def ask_folder(title):
    root = tk.Tk(); root.withdraw()
    return filedialog.askdirectory(title=title)

def ask_text(title, prompt, default=""):
    root = tk.Tk(); root.withdraw()
    return simpledialog.askstring(title, prompt, initialvalue=default)

# =========================
# 🚀 MAIN
# =========================
def main():
    print("🚀 ARM-Nail: GPU + Whisper Caption + High Quality")

    folder_elvenlab = ask_folder("📁 Chọn thư mục ElvenLab (giọng nói)")
    folder_video = ask_folder("📁 Chọn thư mục video nền")
    out_folder = ask_folder("📤 Chọn thư mục lưu kết quả")

    caption_pos = ask_text("📍 Caption", "Chọn vị trí caption (top / center / bottom):", "bottom")
    title_text = ask_text("✍️ Title", "Nhập title để gắn lên video:", "Nail Transformation")
    title_pos = ask_text("📍 Vị trí title", "Chọn vị trí title (top / center / bottom):", "top")

    if not all([folder_elvenlab, folder_video, out_folder]):
        print("❌ Thiếu thông tin.")
        return

    audios = sorted([str(p) for p in Path(folder_elvenlab).glob("*.mp3")])
    videos = sorted([str(p) for p in Path(folder_video).glob("*.mp4")])
    video_durs = {v: get_duration(v) for v in videos}

    for audio in audios:
        audio_dur = get_duration(audio)
        base = Path(audio).stem
        matched = None

        # 🔍 Tìm video gần nhất
        for v in videos:
            if abs(video_durs[v] - audio_dur) <= 5:
                matched = v
                break

        output_raw = Path(out_folder) / f"{base}_merged.mp4"

        if matched:
            v_dur = video_durs[matched]
            speed = round(audio_dur / v_dur, 3) if v_dur > 0 else 1.0
            adjusted_audio = "__temp_audio.mp3"
            change_audio_speed(audio, adjusted_audio, speed)
            merge_audio_video_keep_quality(matched, adjusted_audio, output_raw)
            os.remove(adjusted_audio)
        else:
            print(f"⚠️ Không tìm thấy video khớp → ghép clip")
            total, batch = 0.0, []
            for v in videos:
                batch.append(v)
                total += video_durs[v]
                if abs(total - audio_dur) <= 5:
                    break
            if not batch:
                print("❌ Không đủ video để ghép.")
                continue
            temp_merge = "__temp_combined.mp4"
            merge_videos_concat_nvidia(batch, temp_merge)
            merge_audio_video_keep_quality(temp_merge, audio, output_raw)
            os.remove(temp_merge)

        if not Path(output_raw).exists():
            print(f"❌ Merge thất bại: {output_raw.name}")
            continue

        # 🧠 Tạo caption từ Whisper
        caption_text = generate_auto_caption(audio)

        # 🖋️ Add caption + title
        captioned = "__captioned.mp4"
        add_text_to_video(output_raw, captioned, caption_text, caption_pos)

        final_output = Path(out_folder) / f"{base}_final.mp4"
        add_text_to_video(captioned, final_output, title_text, title_pos)

        os.remove(output_raw)
        os.remove(captioned)
        print(f"✅ Xuất: {final_output}")

if __name__ == "__main__":
    main()
