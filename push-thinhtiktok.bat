@echo off
chcp 65001 >nul
title Quick Git Push

echo Dang push Python & BAT files len GitHub...

REM Thêm các file .py và .bat (tự động tôn trọng .gitignore)
git add *.py *.bat .gitignore

git commit -m "Update: Python scripts and batch files"
git branch -M main
git push origin main

if %errorlevel% equ 0 (
    echo PUSH THANH CONG!
) else (
    echo PUSH THAT BAI! Kiem tra ket noi hoac quyen truy cap.
)

pause