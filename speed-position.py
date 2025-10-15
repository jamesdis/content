import os, re, random, subprocess
from glob import glob

# ==== 🧾 NHẬP TÊN CHỦ ĐỀ ====
topic = input("🔹 Nhập tên topic (VD: REUNION): ").strip()
base_folder = os.path.join("1_SOURCE", topic)

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

# ==== 📂 CHỌN NGUỒN VIDEO ====
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

input_folders = [os.path.join(base_folder, folder) for folder in source_folders]

# ==== 📈 NHẬP SPEED & STEP ====
speed_input = input("⚙️ Nhập khoảng speed (VD: 1.1-1.2): ").strip() or "1.1-1.2"
jump_input = input("🔀 Nhập bước nhảy random (VD: 30-50): ").strip() or "30-50"
SPEED_RANGE = tuple(map(float, speed_input.split("-")))
JUMP_RANGE = tuple(map(int, jump_input.split("-")))

# ==== 📂 GOM CLIP TỪ NGUỒN ====
video_paths = []
for folder in input_folders:
    if os.path.exists(folder):
        video_paths += glob(os.path.join(folder, "*.mp4"))

print(f"🔍 Tổng video cần xử lý: {len(video_paths)}")

# ==== 🚀 TĂNG TỐC + GHI TẠM ====
processed = []
for path in video_paths:
    filename = os.path.basename(path)
    name, _ = os.path.splitext(filename)
    
    speed = round(random.uniform(*SPEED_RANGE), 3)
    out_name = f"{name}_x{speed}.mp4"
    out_path = os.path.join(output_folder, out_name)

    cmd = [
        "ffmpeg", "-hwaccel", "cuda", "-i", path,
        "-filter_complex", f"[0:v]setpts=PTS/{speed},scale=2560:1440[v];[0:a]atempo={speed}[a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "h264_nvenc",
        "-preset", "hq", "-c:a", "aac", "-shortest", "-y", out_path
    ]

    print(f"⚙️ Speed x{speed} → {out_name}")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    processed.append((out_path, speed))
    
# ==== 🔀 XÁO TRỘN CLIP ====
random.shuffle(processed)
reordered, used = [], set()
idx = random.randint(0, min(5, len(processed) - 1))

while len(reordered) < len(processed):
    if idx >= len(processed):
        remain = [i for i in range(len(processed)) if i not in used]
        if not remain: break
        idx = random.choice(remain)
    if idx in used:
        idx += 1
        continue
    reordered.append(processed[idx])
    used.add(idx)
    idx += random.randint(*JUMP_RANGE)

