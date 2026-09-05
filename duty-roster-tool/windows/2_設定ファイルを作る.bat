@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

echo ============================================
echo  設定ファイル（対象者・回数）を作る
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [エラー] 先に「1_セットアップ.bat」を実行してください。
    pause
    exit /b 1
)

set "SCHEDULE=%~1"
if "%SCHEDULE%"=="" (
    echo 勤務割当表の Excel ファイルを、このウィンドウにドラッグして
    echo Enter キーを押してください。
    echo.
    set /p SCHEDULE="勤務表: "
)
set SCHEDULE=%SCHEDULE:"=%
if not exist "%SCHEDULE%" (
    echo [エラー] ファイルが見つかりません: %SCHEDULE%
    pause
    exit /b 1
)

set "FORCE="
if exist "config\roster.yaml" (
    echo.
    echo すでに設定ファイルがあります: config\roster.yaml
    set /p ANSWER="上書きしますか？ (y/n): "
    if /i not "%ANSWER%"=="y" (
        echo やめました。
        pause
        exit /b 0
    )
    set "FORCE=--force"
)

echo.
call ".venv\Scripts\duty-roster.exe" init-config -s "%SCHEDULE%" -o config\roster.yaml %FORCE%
echo.
echo --------------------------------------------
echo config\roster.yaml ができました。
echo 対象者や回数が違う場合は、メモ帳で開いて直してください。
echo （このファイルには氏名が入ります。共有しないでください）
echo --------------------------------------------
echo.
pause
