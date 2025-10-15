import os
import re

def create_folders_case_1(topic_str, lang_count, languages):
    source_root = "1_SOURCE"
    final_root = "2_FINAL"

    topic_source_path = os.path.join(source_root, topic_str)
    os.makedirs(topic_source_path, exist_ok=True)

    for sub in ["DEMO-CAPCUT", "ELEVENLAB", "LONGS", "SHORTS"]:
        sub_path = os.path.join(topic_source_path, sub)
        os.makedirs(sub_path, exist_ok=True)
        print(f"📁 {sub_path}")

        if sub == "DEMO-CAPCUT":
            if lang_count == 0:
                # ✅ Tạo Random và Hook khi không có ngôn ngữ
                for inner in ["Random", "Hook"]:
                    inner_path = os.path.join(sub_path, inner)
                    os.makedirs(inner_path, exist_ok=True)
                    print(f"  📁 {inner_path}")
            else:
                for lang in languages:
                    lang_path = os.path.join(sub_path, lang)
                    os.makedirs(lang_path, exist_ok=True)
                    print(f"  📁 {lang_path}")

        elif sub == "ELEVENLAB":
            for lang in languages:
                lang_path = os.path.join(sub_path, lang)
                os.makedirs(lang_path, exist_ok=True)
                print(f"  📁 {lang_path}")

    # ✅ Tạo thư mục trong 1_FINAL (dạng: 1_FINAL/{topic gốc})
    topic_base = topic_str.split("-")[0]
    topic_final_base = os.path.join(final_root, topic_base)
    os.makedirs(topic_final_base, exist_ok=True)
    print(f"📁 {topic_final_base}")

    for lang in languages:
        lang_final_path = os.path.join(topic_final_base, lang)
        os.makedirs(lang_final_path, exist_ok=True)
        print(f"  📁 {lang_final_path}")

# ===== Nhập chuỗi từ người dùng =====
user_input = input("Nhập chuỗi (VD: zack-2-korean,japan hoặc TEST-0): ").strip()

# Kiểm tra định dạng
match = re.match(r'^(.+)-(\d+)(?:-([\w,]+))?$', user_input)

if not match:
    print("❌ Định dạng không hợp lệ. Đúng định dạng là: topic-số hoặc topic-số-ngônngữ1,ngônngữ2")
    exit()

topic = match.group(1).strip()
lang_count = int(match.group(2).strip())
languages = match.group(3).split(',') if match.group(3) else []

# ✅ Trường hợp không có ngôn ngữ → tạo DEMO-CAPCUT/Random, Hook
if lang_count == 0 and not languages:
    create_folders_case_1(user_input, lang_count, [])
elif lang_count != len(languages):
    print(f"❌ Bạn nhập {len(languages)} ngôn ngữ, nhưng khai báo là {lang_count}.")
else:
    create_folders_case_1(user_input, lang_count, languages)

print("\n✔ Hoàn tất.")
