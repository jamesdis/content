# random-position.py
import os
import random
import shutil
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
    print("❌ Lựa chọn không hợp lệ."); raise SystemExit(1)

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
    print("❌ Lựa chọn không hợp lệ."); raise SystemExit(1)

input_folders = [os.path.join(base_folder, folder) for folder in source_folders]

# ==== 🔢 NHẬP STEP (JUMP RANGE) ====
jump_input = input("🔀 Nhập bước nhảy random (VD: 30-50): ").strip() or "30-50"
try:
    JUMP_RANGE = tuple(map(int, jump_input.split("-")))
    assert len(JUMP_RANGE) == 2 and JUMP_RANGE[0] > 0 and JUMP_RANGE[1] >= JUMP_RANGE[0]
except Exception:
    print("❌ Bước nhảy không hợp lệ. Ví dụ hợp lệ: 30-50"); raise SystemExit(1)

# ==== 📂 GOM CLIP TỪ NGUỒN ====
video_paths = []
for folder in input_folders:
    if os.path.exists(folder):
        video_paths += glob(os.path.join(folder, "*.mp4"))

if not video_paths:
    print("❌ Không tìm thấy video .mp4 nào trong thư mục nguồn."); raise SystemExit(1)

print(f"🔍 Tổng video cần xếp lại: {len(video_paths)}")

# ==== 🔀 XÁO TRỘN THEO STEP ====
# Cơ chế: chọn một chỉ số khởi đầu ngẫu nhiên, sau đó tăng chỉ số theo bước nhảy ngẫu nhiên trong JUMP_RANGE.
# Nếu vượt quá danh sách, sẽ chọn ngẫu nhiên một chỉ số chưa dùng còn lại.
random.shuffle(video_paths)  # trộn nhẹ đầu vào để đa dạng
reordered, used = [], set()
start_idx = random.randint(0, len(video_paths) - 1)

idx = start_idx
while len(reordered) < len(video_paths):
    if idx >= len(video_paths):
        remaining = [i for i in range(len(video_paths)) if i not in used]
        if not remaining:
            break
        idx = random.choice(remaining)

    if idx in used:
        idx += 1
        continue

    reordered.append(video_paths[idx])
    used.add(idx)
    idx += random.randint(*JUMP_RANGE)

# ==== 📤 XUẤT THEO THỨ TỰ MỚI (COPY, GIỮ TÊN GỐC + THÊM STT) ====
# Ví dụ tên output: 01__original-name.mp4
digits = len(str(len(reordered)))
copied = 0
for i, src in enumerate(reordered, start=1):
    base_name = os.path.basename(src)
    dst_name = f"{i:0{digits}d}__{base_name}"
    dst_path = os.path.join(output_folder, dst_name)

    try:
        shutil.move(src, dst_path)  # đổi thành shutil.move nếu muốn DI CHUYỂN
        copied += 1
        print(f"✅ {i:0{digits}d}/{len(reordered)} → {dst_name}")
    except Exception as e:
        print(f"⚠️ Lỗi sao chép '{base_name}': {e}")

print(f"\n🎉 Hoàn tất. Đã sắp xếp & sao chép {copied}/{len(reordered)} video vào: {output_folder}")
