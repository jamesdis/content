import os
import subprocess
import tkinter as tk
from tkinter import filedialog, simpledialog
import ffmpeg

# === Chọn folder ===
def choose_folder(title):
    root = tk.Tk()
    root.withdraw()
    return filedialog.askdirectory(title=title)

def ask_text(title, prompt):
    root = tk.Tk()
    root.withdraw()
    return simpledialog.askstring(title, prompt)

# === Lấy chiều cao video ===
def get_video_height(video_path):
    try:
        probe = ffmpeg.probe(video_path)
        video_streams = [s for s in probe['streams'] if s['codec_type'] == 'video']
        height = int(video_streams[0]['height'])
        return height
    except Exception as e:
        print("❌ Không lấy được chiều cao video:", e)
        return None

# === Tính vị trí caption theo tỷ lệ IG Reels ===
def compute_y(height, position):
    if position == "top":
        return str(height * 0.21)
    elif position in ["center", "middle"]:
        return str(height * 0.50)
    elif position == "bottom":
        return str(height * 0.78)
    else:
        return str(height * 0.21)

# === Xử lý từng video với GPU (NVENC) ===
def add_text_to_video(input_path, output_path, text, position="top"):
    height = get_video_height(input_path)
    if not height:
        print(f"⚠️ Bỏ qua video: {input_path}")
        return

    y_pos = compute_y(height, position)

    filter_str = (
        f"drawtext=fontfile=/Windows/Fonts/arialbd.ttf:"
        f"text='{text}':fontcolor=black:fontsize=42:"
        f"box=1:boxcolor=white@1.0:boxborderw=20:"
        f"x=(w-text_w)/2:y={y_pos}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "cuda",
        "-i", input_path,
        "-vf", filter_str,
        "-c:v", "h264_nvenc", "-preset", "slow", "-cq", "18",
        "-c:a", "copy",
        output_path
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Đã xử lý: {os.path.basename(output_path)}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi xử lý {input_path}: {e}")

# === Chạy chương trình ===
def main():
    source_dir = choose_folder("📂 Chọn thư mục video nguồn")
    if not source_dir:
        print("❌ Bạn chưa chọn thư mục.")
        return

    base_out = choose_folder("📂 Chọn thư mục xuất kết quả")
    if not base_out:
        print("❌ Bạn chưa chọn thư mục xuất.")
        return

    title = ask_text("Tiêu đề", "📝 Nhập caption:")
    if not title:
        print("❌ Bạn chưa nhập caption.")
        return

    position = ask_text("Vị trí", "📍 Nhập vị trí (top, center, bottom):").lower()
    if position not in ["top", "center", "middle", "bottom"]:
        position = "top"

    valid_exts = ('.mp4', '.mov', '.mkv', '.avi')
    videos = [f for f in os.listdir(source_dir) if f.lower().endswith(valid_exts)]

    for video in videos:
        in_path = os.path.join(source_dir, video)
        out_path = os.path.join(base_out, f"caption_{video}")
        add_text_to_video(in_path, out_path, title, position)

if __name__ == "__main__":
    main()
