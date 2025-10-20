@echo off
cd /d D:\Second-Jobs\tho_video

echo ==== Adding changes ====
git add .

echo ==== Committing ====
git commit -m "quick update"

IF %ERRORLEVEL% NEQ 0 (
    echo ⚠️ Nothing to commit.
)

echo ==== Pushing ====
git push

echo.
echo ✅ Push script finished. Press any key to exit.
pause > nul
