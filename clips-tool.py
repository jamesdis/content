import os, re, random, subprocess, time
from pathlib import Path
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from scenedetect.video_splitter import split_video_ffmpeg

# ==== ⚙️ CẤU HÌNH ====
SCENE_THRESHOLD = 50.0
MIN_DURATION = 4.0                # chỉ giữ clip >= 3s
ENCODE_PRESET = "p7"              # p7/p6/slow (tuỳ driver)
QP_VALUE = "18"                   # 16 = đẹp hơn nhưng file to hơn

# ==== 🧾 NHẬP TÊN CHỦ ĐỀ ====
topic = input("Nhập tên topic (VD: REUNION): ").strip()
base_folder = os.path.join(os.getcwd(), "1_SOURCE", topic)

# ==== 📁 CHỌN NƠI XUẤT FILE ====
print("\n📁 Chọn nơi xuất file:")
print("1. DEMO-CAPCUT/Hook")
print("2. DEMO-CAPCUT/Random")
print("3. Nhập tên thư mục tùy chọn")
folder_option = input("Chọn (1/2/3): ").strip()

if folder_option == "1":
    target_subfolder = "Hook"
elif folder_option == "2":
    target_subfolder = "Random"
elif folder_option == "3":
    target_subfolder = input("Nhập tên thư mục đích trong DEMO-CAPCUT: ").strip()
else:
    print("❌ Lựa chọn không hợp lệ."); exit()

output_folder = os.path.join(base_folder, "DEMO-CAPCUT", target_subfolder)
os.makedirs(output_folder, exist_ok=True)

# ==== 🎬 CHỌN NGUỒN VIDEO ====
print("\n🎬 Chọn nguồn video:")
print("1. LONGS\n2. SHORTS\n3. CẢ 2")
source_option = input("Chọn (1/2/3): ").strip()
source_folders = []
if source_option == "1":
    source_folders.append("LONGS")
elif source_option == "2":
    source_folders.append("SHORTS")
elif source_option == "3":
    source_folders.extend(["LONGS", "SHORTS"])
else:
    print("❌ Lựa chọn không hợp lệ."); exit()

# ==== 📈 Nhập SPEED & STEP ====
speed_input = input("Nhập khoảng speed (VD: 1.1-1.2): ").strip()
jump_input = input("Nhập khoảng bước nhảy (VD: 30-50): ").strip()
SPEED_RANGE = tuple(map(float, speed_input.split("-"))) if speed_input else (1.1, 1.2)
JUMP_RANGE = tuple(map(int, jump_input.split("-"))) if jump_input else (30, 50)

# ==== THƯ MỤC TẠM + THỐNG KÊ ====
temp_dir = os.path.join(base_folder, "TEMP_SPLIT")
os.makedirs(temp_dir, exist_ok=True)
processed = []
report_data = []
total_videos = 0
total_scenes = 0
total_valid = 0

def _probe_duration(path: str) -> float:
    """Lấy duration (giây) bằng ffprobe; lỗi -> 0.0"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True
        ).stdout.strip()
        return float(out)
    except Exception:
        return 0.0

def _atempo_chain(speed: float) -> str:
    """
    atempo chỉ nhận 0.5..2.0 -> xâu chuỗi để đạt mọi speed > 0
    ví dụ: 2.5 -> atempo=2.0,atempo=1.25
    """
    s = float(speed) if speed > 0 else 1.0
    chain = []
    while s > 2.0:
        chain.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        chain.append("atempo=0.5")
        s /= 0.5
    chain.append(f"atempo={s:.6f}")
    return ",".join(chain)

# ==== 🚀 XỬ LÝ VIDEO ====
for folder in source_folders:
    input_dir = os.path.join(base_folder, folder)
    if not os.path.exists(input_dir):
        continue

    video_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".mp4")]
    total_videos += len(video_files)

    for video in video_files:
        name = os.path.splitext(video)[0]
        input_path = os.path.join(input_dir, video)

        print(f"\n🎬 Phân tích cảnh: {video}")

        # ✅ API mới: KHÔNG dùng VideoManager/ list path
        vid = open_video(input_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=SCENE_THRESHOLD))
        scene_manager.detect_scenes(video=vid)
        scenes = scene_manager.get_scene_list()

        num_scenes = len(scenes)
        total_scenes += num_scenes
        if num_scenes == 0:
            print("⚠️ Không có scene nào được phát hiện.")
            report_data.append([video, "", "", 0, 0])
            continue

        # ✅ split_video_ffmpeg: TRUYỀN STRING PATH, không phải list
        # Làm 'safe' tên tệp để tránh ký tự gây lỗi
        safe_name = re.sub(r'[\\/:*?"<>|#@\(\)\[\]\{\}]', "_", name).strip(" .\t")
        out_tmpl = os.path.join(temp_dir, f"{safe_name}_$SCENE_NUMBER.mp4")

        try:
            split_video_ffmpeg(input_path, scenes, output_file_template=out_tmpl)
        except Exception as e:
            print("❌ Lỗi tách scene:", e)
            continue

        # Lọc & encode từng clip
        clips = sorted([f for f in os.listdir(temp_dir) if f.startswith(safe_name) and f.endswith(".mp4")])
        valid_scenes = 0

        for idx, clip in enumerate(clips, start=1):
            clip_path = os.path.join(temp_dir, clip)
            duration = _probe_duration(clip_path)

            if duration < MIN_DURATION:
                try:
                    os.remove(clip_path)
                except Exception:
                    pass
                print(f"⏩ Xoá clip < {MIN_DURATION}s: {clip}")
                continue

            valid_scenes += 1
            total_valid += 1
            speed = round(random.uniform(*SPEED_RANGE), 3)

            # ✅ giữ NGUYÊN độ phân giải, KHÔNG upscale
            vf = f"[0:v]setpts=PTS/{speed}[v]"
            af = f"[0:a]{_atempo_chain(speed)}[a]"
            temp_out = os.path.join(output_folder, f"{safe_name}_clip{idx:02d}_x{speed}.mp4")

            cmd = [
                "ffmpeg", "-y", "-hwaccel", "cuda", "-i", clip_path,
                "-filter_complex", f"{vf};{af}",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "h264_nvenc", "-preset", ENCODE_PRESET,
                "-rc", "constqp", "-qp", QP_VALUE,
                "-profile:v", "high", "-pix_fmt", "yuv420p",
                "-bf", "3", "-spatial_aq", "1", "-aq-strength", "8",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", "-shortest",
                temp_out
            ]

            print(f"⚙️ Speed x{speed} → {os.path.basename(temp_out)}")
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            processed.append((temp_out, speed))

        # Ghi báo cáo cơ bản
        all_numbers = re.findall(r"(\d{6,})", name)
        id_final = all_numbers[-1][-6:] if all_numbers else "xxxxxx"
        title = re.sub(r"#\S+", "", re.sub(r"\d{6,}$", "", name)).strip("-_ ")
        report_data.append([video, id_final, title, num_scenes, valid_scenes])

# ==== 🔀 XÁO TRỘN + ĐỔI TÊN ====
random.shuffle(processed)
reordered, used = [], set()
if processed:
    idx = random.randint(0, min(5, len(processed) - 1))
else:
    idx = 0

while len(reordered) < len(processed):
    if idx >= len(processed):
        remaining = [i for i in range(len(processed)) if i not in used]
        if not remaining:
            break
        idx = random.choice(remaining)
    if idx in used:
        idx += 1
        continue
    reordered.append(processed[idx])
    used.add(idx)
    idx += random.randint(*JUMP_RANGE)

# ==== 📛 ĐỔI TÊN CHUẨN ====
for i, (file_path, speed) in enumerate(reordered, start=1):
    filename = os.path.basename(file_path)
    name_no_ext = os.path.splitext(filename)[0]

    # Lấy 6 số cuối cùng từ chuỗi số dài
    all_numbers = re.findall(r"(\d{6,})", name_no_ext)
    id_part = all_numbers[-1][-6:] if all_numbers else "xxxxxx"

    # Bỏ suffix speed cũ
    title_part = re.sub(r"_x\d+(\.\d+)?$", "", name_no_ext)
    # Bỏ hashtag, ngày tháng, @username, STT đầu, chuỗi số dài ở cuối
    title_clean = re.sub(r"#\S+", "", title_part)
    title_clean = re.sub(r"\d{4}-\d{2}-\d{2}", "", title_clean)
    title_clean = re.sub(r"@\S+", "", title_clean)
    title_clean = re.sub(r"^\d{1,2}-", "", title_clean)
    title_clean = re.sub(r"\d{6,}$", "", title_clean)
    title_clean = title_clean.strip(" _-")

    new_filename = f"{i:02d}_{title_clean}_{id_part}_x{speed}.mp4" if title_clean else f"{i:02d}_{id_part}_x{speed}.mp4"
    new_path = os.path.join(output_folder, new_filename)
    try:
        os.rename(file_path, new_path)
    except Exception:
        # nếu rename thất bại (tên trùng/locked), giữ nguyên
        pass

# ==== 🧹 XOÁ VIDEO CŨ (nguồn & temp) ====
# CẨN THẬN: nếu muốn giữ file nguồn, hãy comment khối này.
time.sleep(1)
for folder in source_folders + ["TEMP_SPLIT"]:
    dir_path = os.path.join(base_folder, folder)
    if not os.path.isdir(dir_path):
        continue
    for f in os.listdir(dir_path):
        if f.lower().endswith(".mp4"):
            try:
                os.remove(os.path.join(dir_path, f))
            except Exception:
                print(f"⚠️ Không thể xoá file: {f}")

# ==== 📝 GHI FILE BÁO CÁO ====
print(f"\n✅📄 Tổng video: {total_videos} | Tổng cảnh: {total_scenes} | Cảnh hợp lệ (≥ {MIN_DURATION}s): {total_valid}")
print(f"📂 Xuất tới: {output_folder}")
