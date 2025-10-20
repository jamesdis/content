@echo off
cd /d "%~dp0"

:: Tạo folder nếu chưa có
if not exist "tuwi" (
    mkdir tuwi
    echo [INFO] Đã tạo thư mục tuwi
)

cd tuwi

:: Tạo file .gitignore để chỉ theo dõi .py và .bat
echo * > .gitignore
echo !*.py >> .gitignore
echo !*.bat >> .gitignore

:: Khởi tạo git nếu chưa có
if not exist ".git" (
    git init
    git remote add origin https://github.com/AndrewThinhNguyen/tiktok_code.git
)

:: Cập nhật nhánh và commit
git add *.py *.bat
git commit -m "💾 Push .py + .bat from tuwi"
git branch -M main
git push -u origin main

echo ✅ Done!
pause
