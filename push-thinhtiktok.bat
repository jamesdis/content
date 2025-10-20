@echo off
chcp 65001 >nul
title QUICK PUSH - AndrewThinhNguyen/tiktok_code
color 0A

echo ===============================================
echo    QUICK PUSH TO AndrewThinhNguyen/tiktok_code
echo ===============================================
echo.

REM Chuyển đến thư mục gốc của script
cd /d "%~dp0"

REM Kiểm tra xem có thư mục .git không
if not exist ".git" (
    echo [INIT] Dang khoi tao git repository...
    git init
    git remote add origin https://github.com/AndrewThinhNguyen/tiktok_code.git
    echo Da khoi tao repository voi remote origin!
)

REM Kiểm tra kết nối remote
git remote -v

REM Thêm tất cả file .py, .bat và .gitignore
echo.
echo [ADD] Dang them file .py, .bat va .gitignore...
git add *.py
git add *.bat
git add .gitignore

REM Kiểm tra xem có thay đổi nào để commit không
git diff --cached --quiet
if %errorlevel% equ 0 (
    echo.
    echo [INFO] Khong co thay doi nao de commit!
    echo Cac file da duoc commit truoc do hoac khong co thay doi.
    goto :push
)

REM Tạo commit với timestamp
echo.
set "timestamp=%date% %time%"
set "commit_msg=Auto push: Python & BAT files - %timestamp%"

echo [COMMIT] Dang tao commit...
echo Message: %commit_msg%
git commit -m "%commit_msg%"

:push
REM Đẩy code lên GitHub
echo.
echo [PUSH] Dang push code len GitHub...
git branch -M main
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ===============================================
    echo    PUSH SUCCESS! ✓
    echo ===============================================
    echo Repository: https://github.com/AndrewThinhNguyen/tiktok_code
    echo.
    echo Files pushed:
    git log -1 --name-only --oneline
) else (
    echo.
    echo ===============================================
    echo    PUSH FAILED! ✗
    echo ===============================================
    echo Possible issues:
    echo - No internet connection
    echo - Authentication required
    echo - Check remote URL
    echo.
    echo Try: git push -u origin main
)

echo.
pause