import os
import sys
import subprocess
import platform
import webbrowser
from importlib import import_module

# Danh sách các thư viện Python cần thiết
PYTHON_REQUIREMENTS = [
    "os",
    "shutil",
    "re",
    "random",
    "time",
    "uuid",
    "glob",
    "csv",
    "multiprocessing",
    "googleapiclient.discovery",
    "googleapiclient.errors",
    "moviepy.editor",
    "scenedetect",
    "ffmpeg",               # ffmpeg-python
    "yt_dlp",               # yt-dlp Python API
    "torch",                # dùng cho GPU (Demucs, PyTorch-based tools)
    "torchaudio",           # âm thanh (Demucs/GPU audio processing)
    "numpy",                # xử lý frame nhanh
    "opencv-python",        # dùng để xử lý video bằng OpenCV (GPU supported)
    "tqdm",                 # progress bar
    "colorama",             # tô màu terminal
]


# Thông tin cài đặt thủ công chi tiết
MANUAL_INSTALLS = {
    "ffmpeg": {
        "description": "FFmpeg là công cụ xử lý video/audio cần thiết",
        "steps": [
            "1. Truy cập trang chính thức: https://www.gyan.dev/ffmpeg/builds/",
            "2. Download: ffmpeg-release-essentials.zip",
            "3. Tạo thư mục mới: D:\\Tools\\ffmpeg",
            "4. Giải nén file .zip vào thư mục đó: D:\\Tools\\ffmpeg\\bin",
            "5. Thêm vào PATH:",
            "   - Mở Edit the system environment variables",
            "   - Environment Variables -> System variables",
            "   - Chọn Path → Edit → New → dán 'D:\\Tools\\ffmpeg\\bin'",
            "6. Kiểm tra: mở Command Prompt và chạy 'ffprobe -version'"
        ],
        "url": "https://www.gyan.dev/ffmpeg/builds/"
    },
    "nvidia_driver": {
        "description": "Cập nhật driver NVIDIA để tận dụng GPU",
        "steps": [
            "1. Truy cập: https://www.nvidia.com/Download/index.aspx?lang=en-us",
            "2. Chọn đúng Product Series theo cấu hình máy:",
            "   - Xem cấu hình: Windows + R → dxdiag → Tab Display",
            "3. Download bản Game Ready Driver (GRD) hoặc Studio Driver (SD)",
            "4. Cài đặt:",
            "   - Chọn Custom (Advanced)",
            "   - Tích vào 'Perform a clean installation'",
            "   - Hoàn tất cài đặt (máy sẽ nhấp nháy màn hình)"
        ],
        "url": "https://www.nvidia.com/Download/index.aspx?lang=en-us"
    },
    "demucs": {
        "description": "Công cụ tách âm thanh (nếu cần)",
        "steps": [
            "pip install demucs",
            "Nếu có GPU NVIDIA, cài thêm:",
            "pip install torch torchaudio -f https://download.pytorch.org/whl/cu111/torch_stable.html"
        ]
    }
}

def print_install_instructions(tool_name):
    """Hiển thị hướng dẫn cài đặt chi tiết"""
    tool = MANUAL_INSTALLS.get(tool_name)
    if not tool:
        return
    
    print(f"\n📌 {tool_name.upper()}: {tool['description']}")
    print("🔧 Các bước cài đặt:")
    for step in tool["steps"]:
        print(f"    {step}")
    
    if "url" in tool:
        open_browser = input(f"\n👉 Bạn có muốn mở trình duyệt đến trang download {tool_name}? (y/n): ").lower()
        if open_browser == 'y':
            webbrowser.open(tool["url"])

def check_python_dependencies():
    missing = []
    for lib in PYTHON_REQUIREMENTS:
        try:
            import_module(lib.split('.')[0])
        except ImportError:
            missing.append(lib)
    return missing

def install_pip_packages(missing_packages):
    for package in missing_packages:
        print(f"⚙️ Đang cài đặt {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ Đã cài đặt thành công {package}")
        except subprocess.CalledProcessError:
            print(f"❌ Không thể cài đặt {package}")

def check_system_tools():
    missing_tools = []
    
    # Kiểm tra ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing_tools.append("ffmpeg")
    
    # Kiểm tra GPU NVIDIA
    if platform.system() == "Windows":
        try:
            subprocess.run(["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            try:
                import torch
                if not torch.cuda.is_available():
                    missing_tools.append("nvidia_driver")
            except ImportError:
                pass
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    return missing_tools

def main():
    print("""
    ====================================
    🔍 KIỂM TRA VÀ CÀI ĐẶT YÊU CẦU HỆ THỐNG
    ====================================
    """)
    
    # Kiểm tra thư viện Python
    missing_python = check_python_dependencies()
    if missing_python:
        print("\n📦 Các thư viện Python cần cài đặt:")
        for lib in missing_python:
            print(f"- {lib}")
        
        install_now = input("\n👉 Bạn có muốn cài đặt tự động các thư viện này? (y/n): ").strip().lower()
        if install_now == 'y':
            install_pip_packages(missing_python)
        else:
            print("⚠️ Bạn cần cài đặt các thư viện trên để chạy chương trình.")
    else:
        print("✅ Tất cả thư viện Python đã được cài đặt.")
    
    # Kiểm tra công cụ hệ thống
    missing_tools = check_system_tools()
    if missing_tools:
        print("\n⚠️ CÁC CÔNG CỤ CẦN CÀI ĐẶT THỦ CÔNG:")
        for tool in missing_tools:
            print_install_instructions(tool)
    
    # Kiểm tra CUDA nếu có GPU NVIDIA
    if platform.system() == "Windows":
        try:
            subprocess.run(["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            print("\nℹ️ PHÁT HIỆN GPU NVIDIA")
            try:
                import torch
                if torch.cuda.is_available():
                    print(f"✅ Đã cài đặt PyTorch với CUDA (phiên bản {torch.version.cuda})")
                else:
                    print("⚠️ PyTorch chưa hỗ trợ CUDA")
                    print_install_instructions("nvidia_driver")
            except ImportError:
                print("⚠️ PyTorch chưa được cài đặt. Nếu cần chạy Demucs trên GPU:")
                print_install_instructions("demucs")
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    print("\n" + "="*50)
    print("✔ KIỂM TRA HOÀN TẤT. BẠN CÓ THỂ CHẠY CÁC SCRIPT CỦA MÌNH")
    print("="*50)

if __name__ == "__main__":
    main()