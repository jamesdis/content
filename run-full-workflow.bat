@echo off
chcp 65001 >nul
cd /d %~dp0

echo ======================================================
echo 🎬 BẮT ĐẦU WORKFLOW TỰ ĐỘNG: TÁCH CLIP + GHÉP VIDEO
echo ======================================================
echo.

echo 🔹 Bước 1: Đang chạy chương trình TÁCH CLIP (gui-clip-tool.py)...
python gui-clip-tool.py
if errorlevel 1 (
    echo ❌ Lỗi khi chạy gui-clip-tool.py. Dừng workflow.
    pause
    exit /b
)
echo ✅ Hoàn tất bước 1: Tách clip xong!
echo.

echo 🔹 Bước 2: Đang chạy chương trình GHÉP VIDEO (gui-wf-merge.py)...
python gui-merge.py
if errorlevel 1 (
    echo ❌ Lỗi khi chạy gui-merge.py. Dừng workflow.
    pause
    exit /b
)
echo ✅ Hoàn tất bước 2: Merge video xong!
echo.

echo ======================================================
echo ✅ TOÀN BỘ WORKFLOW ĐÃ HOÀN TẤT THÀNH CÔNG!
echo ======================================================
echo.
pause
