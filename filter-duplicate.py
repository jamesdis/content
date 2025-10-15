import os
import hashlib
import shutil
from pathlib import Path

def get_file_hash(file_path):
    """Tạo hash MD5 cho file để so sánh nội dung"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"Lỗi khi đọc file {file_path}: {e}")
        return None

def get_user_path():
    """Lấy đường dẫn từ người dùng nhập trong terminal"""
    while True:
        path = input("📁 Nhập đường dẫn đến thư mục cần xử lý: ").strip()
        
        # Xử lý đường dẫn nếu người dùng dùng dấu nháy
        path = path.strip('"\'')
        
        if os.path.exists(path):
            return Path(path)
        else:
            print("❌ Đường dẫn không tồn tại! Vui lòng nhập lại.")

def scan_all_subfolders(base_path):
    """Quét tất cả folder con trong đường dẫn"""
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
    
    print("🔍 Đang quét tất cả folder con...")
    print("=" * 60)
    
    # Tìm tất cả folder con trực tiếp trong base_path
    subfolders = [f for f in base_path.iterdir() if f.is_dir()]
    
    print(f"📁 Tìm thấy {len(subfolders)} folder con:")
    
    all_files_by_name = {}  # Dictionary để lưu file theo tên
    folder_stats = {}
    
    for folder in subfolders:
        print(f"\n📂 Đang quét: {folder.name}")
        folder_files = 0
        
        for file_path in folder.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                folder_files += 1
                file_name = file_path.name
                
                # Thêm vào dictionary theo tên file
                if file_name not in all_files_by_name:
                    all_files_by_name[file_name] = {
                        'original_path': file_path,
                        'original_folder': folder.name,
                        'duplicates': []
                    }
                else:
                    all_files_by_name[file_name]['duplicates'].append({
                        'path': file_path,
                        'folder': folder.name
                    })
        
        folder_stats[folder.name] = folder_files
        print(f"   ✅ Tìm thấy {folder_files} video")
    
    return all_files_by_name, folder_stats, subfolders

def analyze_duplicates_by_name(all_files_by_name):
    """Phân tích và phân loại duplicate theo tên file"""
    duplicates = []
    unique_files = {}
    
    for file_name, file_info in all_files_by_name.items():
        unique_files[file_name] = file_info['original_path']
        
        if file_info['duplicates']:
            for dup in file_info['duplicates']:
                # So sánh nội dung để xác nhận trùng thật sự
                original_hash = get_file_hash(file_info['original_path'])
                duplicate_hash = get_file_hash(dup['path'])
                
                duplicates.append({
                    'file_name': file_name,
                    'original': file_info['original_path'],
                    'original_folder': file_info['original_folder'],
                    'duplicate': dup['path'],
                    'duplicate_folder': dup['folder'],
                    'size': dup['path'].stat().st_size,
                    'same_content': original_hash == duplicate_hash if original_hash and duplicate_hash else False
                })
    
    return duplicates, unique_files

def display_statistics(folder_stats, duplicates, unique_files, subfolders):
    """Hiển thị thống kê chi tiết"""
    print("\n" + "=" * 60)
    print("📊 BÁO CÁO THỐNG KÊ")
    print("=" * 60)
    
    print(f"\n📁 DANH SÁCH {len(subfolders)} FOLDER CON:")
    for folder in subfolders:
        count = folder_stats.get(folder.name, 0)
        print(f"   📂 {folder.name}: {count} video")
    
    total_videos = sum(folder_stats.values())
    print(f"\n🎯 TỔNG SỐ VIDEO: {total_videos}")
    print(f"🔍 FILE DUY NHẤT: {len(unique_files)}")
    print(f"⚠️  FILE TRÙNG TÊN: {len(duplicates)}")
    
    if duplicates:
        # Phân loại trùng lặp
        same_content_count = sum(1 for dup in duplicates if dup['same_content'])
        different_content_count = len(duplicates) - same_content_count
        
        print(f"\n📋 PHÂN TÍCH TRÙNG LẶP:")
        print(f"   ✅ Trùng tên và nội dung: {same_content_count} file")
        print(f"   ⚠️  Trùng tên nhưng khác nội dung: {different_content_count} file")
        
        print(f"\n🔍 PHÂN LOẠI THEO FOLDER:")
        duplicate_by_folder = {}
        for dup in duplicates:
            folder_pair = f"{dup['original_folder']} → {dup['duplicate_folder']}"
            duplicate_by_folder[folder_pair] = duplicate_by_folder.get(folder_pair, 0) + 1
        
        for folder_pair, count in duplicate_by_folder.items():
            print(f"   {folder_pair}: {count} file")

def delete_duplicates(duplicates, dry_run=True):
    """Xóa các file trùng lặp"""
    total_saved_space = 0
    deleted_count = 0
    
    print("\n🗑️  XỬ LÝ FILE TRÙNG LẶP")
    print("=" * 60)
    
    for i, dup in enumerate(duplicates, 1):
        original = dup['original']
        duplicate = dup['duplicate']
        size = dup['size']
        same_content = dup['same_content']
        
        print(f"\n#{i}: {dup['file_name']}")
        print(f"   📁 Vị trí: {dup['duplicate_folder']}")
        print(f"   📁 Trùng với: {dup['original_folder']}")
        print(f"   📦 Kích thước: {size / (1024*1024):.2f} MB")
        print(f"   🔍 Trạng thái: {'✅ NỘI DUNG GIỐNG' if same_content else '⚠️ TÊN GIỐNG, NỘI DUNG KHÁC'}")
        
        if not dry_run and same_content:  # Chỉ xóa nếu nội dung giống nhau
            try:
                os.remove(duplicate)
                total_saved_space += size
                deleted_count += 1
                print("   ✅ ĐÃ XÓA FILE TRÙNG LẶP")
            except Exception as e:
                print(f"   ❌ Lỗi khi xóa file: {e}")
        elif not same_content and not dry_run:
            print("   🔒 BỎ QUA (tên giống nhưng nội dung khác)")
        else:
            print("   🔒 CHẾ ĐỘ KIỂM TRA (chưa xóa thật)")
    
    return total_saved_space, deleted_count

def organize_unique_files(all_files_by_name, base_path, subfolders):
    """Tổ chức lại các file không trùng lặp"""
    output_dir = base_path / "Organized_Unique_Videos"
    output_dir.mkdir(exist_ok=True)
    
    print(f"\n📂 Tổ chức file duy nhất vào: {output_dir}")
    
    # Tạo subfolders theo tên folder gốc
    for folder in subfolders:
        (output_dir / folder.name).mkdir(exist_ok=True)
    
    copied_count = 0
    
    for file_name, file_info in all_files_by_name.items():
        try:
            original_path = file_info['original_path']
            original_folder = file_info['original_folder']
            
            dest_path = output_dir / original_folder / file_name
            
            # Nếu tên file đã tồn tại trong folder đích, thêm số
            counter = 1
            while dest_path.exists():
                stem = original_path.stem
                new_name = f"{stem}_{counter}{original_path.suffix}"
                dest_path = output_dir / original_folder / new_name
                counter += 1
            
            shutil.copy2(original_path, dest_path)
            copied_count += 1
            print(f"✅ Đã copy: {original_folder}/{dest_path.name}")
            
        except Exception as e:
            print(f"❌ Lỗi khi copy {file_name}: {e}")
    
    print(f"\n📁 Đã copy {copied_count} file duy nhất vào thư mục tổ chức")

def main():
    print("""
    🎬 VIDEO DUPLICATE CLEANER - AUTO SCAN EDITION
    ==============================================
    Công cụ tự động quét folder con và xóa video trùng lặp
    """)
    
    # Lấy đường dẫn từ người dùng
    base_path = get_user_path()
    
    print(f"\n🎯 Đang xử lý thư mục: {base_path}")
    
    # Quét tất cả folder con
    all_files_by_name, folder_stats, subfolders = scan_all_subfolders(base_path)
    
    # Phân tích duplicate theo tên
    duplicates, unique_files = analyze_duplicates_by_name(all_files_by_name)
    
    # Hiển thị thống kê
    display_statistics(folder_stats, duplicates, unique_files, subfolders)
    
    if not duplicates:
        print("\n🎉 Không tìm thấy file video nào trùng tên!")
        return
    
    # Hiển thị preview trước khi xóa
    print("\n--- CHẾ ĐỘ KIỂM TRA (DRY RUN) ---")
    total_saved, deleted_count = delete_duplicates(duplicates, dry_run=True)
    
    # Hỏi người dùng có muốn xóa thật không
    if any(dup['same_content'] for dup in duplicates):
        response = input("\n🚀 Bạn có muốn xóa các file trùng lặp (nội dung giống) không? (y/n): ")
        
        if response.lower() == 'y':
            print("\n--- THỰC HIỆN XÓA THẬT ---")
            total_saved, deleted_count = delete_duplicates(duplicates, dry_run=False)
            print(f"\n✅ ĐÃ HOÀN THÀNH!")
            print(f"📊 Đã xóa {deleted_count} file trùng lặp")
            print(f"💾 Tiết kiệm được {total_saved / (1024*1024):.2f} MB")
        else:
            print("\n🔒 Đã hủy thao tác xóa file.")
    else:
        print("\nℹ️  Không có file nào trùng cả tên lẫn nội dung để xóa.")
    
    # Hỏi có muốn tổ chức file duy nhất không
    organize = input("\n📁 Bạn có muốn tổ chức các file duy nhất vào thư mục mới? (y/n): ")
    if organize.lower() == 'y':
        organize_unique_files(all_files_by_name, base_path, subfolders)

# Chạy chương trình
if __name__ == "__main__":
    main()
    print("\n✨ Hoàn thành công việc!")