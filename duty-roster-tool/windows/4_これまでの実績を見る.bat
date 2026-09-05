@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo [エラー] 先に「1_セットアップ.bat」を実行してください。
    pause
    exit /b 1
)

echo ============================================
echo  日曜・祝日の予備の通算回数
echo ============================================
echo.
call ".venv\Scripts\duty-roster.exe" history -c config\roster.yaml
echo.
pause
