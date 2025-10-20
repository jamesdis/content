import os
import subprocess
import shutil
from pathlib import Path
import ffmpeg
import tkinter as tk
from tkinter import filedialog, simpledialog
from datetime import datetime

# ========= CONFIG =========
FONT_PATH = "/Windows/Fonts/arialbd.ttf"
USE_GPU = True  # Ưu tiên dùng GPU
VALID_EXT = ('.mp4', '.mov', '.avi', '.mkv')
SCENE_THRESHOLD = 0.30
MIN_DURATION = 1.5

# ========= GUI INPUTS =========
def choose_folder(title):
    root = tk.Tk(); root.withdraw()
    return filedialog.askdirectory(title=title)

def ask_text(prompt, default=""):
    root = tk.Tk(); root.withdraw()
    return simpledialog.askstring("Nhập nội dung", prompt, initialvalue=default)

def compute_y(height, position):
    if position == "top": return str(int(height * 0.21))
    if position in ["center", "middle"]: return str(int(height * 0.50))
    if position == "bottom": return str(int(height * 0.78))
    return str(int(height * 0.21))

def get_video_height(path):
    try:
        probe = ffmpeg.probe(path)
        video_streams = [s for s in probe['streams'] if s['codec_type'] == 'video']
        return int(video_streams[0]['height'])
    except:
        return 1080  # fallback

# ========= VIDEO PROCESSING =========
def detect_scenes(input_path):
    scene_log = Path(input_path).with_suffix(".scene.log")
    cmd = [
        "ffmpeg", "-hide_banner", "-an", "-i", input_path,
        "-filter:v", f"select='gt(scene,{SCENE_THRESHOLD})',showinfo",
        "-f", "null", "-"
    ]
    with open(scene_log, "w", encoding="utf-8") as f:
        subprocess.run(cmd, stderr=f, stdout=subprocess.DEVNULL)

    times = [0.0]
    with open(scene_log, "r", encoding="utf-8") as f:
        for line in f:
            if "pts_time:" in line:
                try:
                    t = float(line.split("pts_time:")[1].split()[0])
                    if not times or t - times[-1] > 0.15:
                        times.append(t)
                except:
                    pass
    try: os.remove(scene_log)
    except: pass

    try:
        dur = float(ffmpeg.probe(input_path)["format"]["duration"])
        if times[-1] < dur:
            times.append(dur)
    except:
        pass

    return [(a, b) for a, b in zip(times[:-1], times[1:]) if b - a >= MIN_DURATION]

def cut_clip(input_path, out_path, start, end):
    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-ss", str(start), "-to", str(end),
        "-i", input_path,
        "-c:v", "h264_nvenc" if USE_GPU else "libx264", "-preset", "p7" if USE_GPU else "slow",
        "-qp" if USE_GPU else "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-fflags", "+genpts",
        "-avoid_negative_ts", "make_zero",
        "-reset_timestamps", "1",
        out_path
    ]
    subprocess.run(cmd, check=True)

def add_caption(input_path, output_path, text, position="top"):
    y_pos = compute_y(get_video_height(input_path), position)
    filter_str = (
        f"drawtext=fontfile='{FONT_PATH}':"
        f"text='{text}':fontcolor=black:fontsize=42:"
        f"box=1:boxcolor=white@1.0:boxborderw=20:"
        f"x=(w-text_w)/2:y={y_pos}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "cuda" if USE_GPU else "auto",
        "-i", input_path,
        "-vf", filter_str,
        "-c:v", "h264_nvenc" if USE_GPU else "libx264",
        "-preset", "slow", "-cq", "18",
        "-c:a", "copy",
        str(output_path)
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Thêm text xong: {output_path.name}")
    except:
        print(f"❌ Lỗi khi xử lý caption: {input_path}")

def concat_videos(v1_path, v2_path, output_path):
    list_txt = output_path.parent / f"__temp_{datetime.now().timestamp()}.txt"
    with open(list_txt, "w", encoding="utf-8") as f:
        f.write(f"file '{os.path.abspath(v1_path)}'\n")
        f.write(f"file '{os.path.abspath(v2_path)}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_txt),
        "-c", "copy",
        str(output_path)
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"🎬 Xuất video: {output_path.name}")
    except:
        print(f"❌ Lỗi khi ghép video: {v1_path} + {v2_path}")
    finally:
        list_txt.unlink(missing_ok=True)

# ========= MAIN =========
def main():
    input_dir = choose_folder("📁 Chọn thư mục chứa video gốc")
    if not input_dir:
        print("❌ Bạn chưa chọn thư mục nguồn."); return

    output_dir = choose_folder("📂 Chọn thư mục xuất kết quả")
    if not output_dir:
        print("❌ Bạn chưa chọn thư mục đích."); return

    text_before = ask_text("Text cho clip BEFORE", "BEFORE")
    text_after = ask_text("Text cho clip AFTER", "AFTER")
    position = ask_text("Vị trí caption (top, center, bottom)", "top").lower()

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for video in input_dir.glob("*"):
        if video.suffix.lower() not in VALID_EXT:
            continue

        spans = detect_scenes(str(video))
        if len(spans) != 2:
            print(f"⏩ Bỏ qua: {video.name} (cảnh: {len(spans)})")
            continue

        base = video.stem
        work_dir = output_dir / base
        work_dir.mkdir(parents=True, exist_ok=True)

        before_clip = work_dir / f"{base}_before.mp4"
        after_clip = work_dir / f"{base}_after.mp4"
        final_output = output_dir / f"{base}_final.mp4"

        try:
            cut_clip(str(video), str(before_clip), spans[0][0], spans[0][1])
            cut_clip(str(video), str(after_clip), spans[1][0], spans[1][1])

            captioned_before = work_dir / f"{base}_caption_before.mp4"
            captioned_after = work_dir / f"{base}_caption_after.mp4"

            add_caption(before_clip, captioned_before, text_before, position)
            add_caption(after_clip, captioned_after, text_after, position)

            concat_videos(captioned_before, captioned_after, final_output)

            # cleanup
            before_clip.unlink(missing_ok=True)
            after_clip.unlink(missing_ok=True)
            captioned_before.unlink(missing_ok=True)
            captioned_after.unlink(missing_ok=True)

            print(f"✅ Đã xử lý: {video.name}")

        except Exception as e:
            print(f"❌ Lỗi xử lý {video.name}: {e}")

    print("\n🎉 Hoàn tất BEFORE–AFTER cho tất cả video!")

if __name__ == "__main__":
    main()
