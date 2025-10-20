@echo off
cd /d "%~dp0"

:: Bước 1: Khởi tạo git nếu chưa có
if not exist .git (
    git init
    git remote add origin https://github.com/AndrewThinhNguyen/tiktok_code.git
)

:: Bước 2: Tạo .gitignore để chỉ theo dõi .py và .bat
echo *.py > .gitignore
echo *.bat >> .gitignore

:: Bước 3: Fetch nhánh main nếu repo đã có nội dung (tránh bị từ chối push)
git fetch origin main
git reset --soft origin/main

:: Bước 4: Add và commit
git add *.py *.bat
git commit -m "🚀 Push .py + .bat files"

:: Bước 5: Push
git branch -M main
git push -u origin main

echo ✅ Đã push xong!
pause
