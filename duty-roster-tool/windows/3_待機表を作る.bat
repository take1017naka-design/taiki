@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo ============================================
echo  カテ待機表を作る
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [エラー] 先に「1_セットアップ.bat」を実行してください。
    pause
    exit /b 1
)
if not exist "config\roster.yaml" (
    echo [エラー] 先に「2_設定ファイルを作る.bat」を実行してください。
    pause
    exit /b 1
)

set "SCHEDULE=%~1"
if "%SCHEDULE%"=="" (
    echo 勤務割当表の Excel ファイルを、このウィンドウにドラッグして
    echo Enter キーを押してください。
    echo （このファイルのアイコンに直接ドラッグしても実行できます）
    echo.
    set /p SCHEDULE="勤務表: "
)
set SCHEDULE=!SCHEDULE:"=!
if not exist "!SCHEDULE!" (
    echo [エラー] ファイルが見つかりません: !SCHEDULE!
    pause
    exit /b 1
)

echo.
echo 先に決めておく担当があれば入力してください。無ければ Enter だけ。
echo   例）待機   5=担当B 12=担当C
set /p FIXTEXT="待機の指定: "
echo   例）予備   5=担当C
set /p FIXBTEXT="予備の指定: "

set "ARGS="
for %%A in (%FIXTEXT%) do set "ARGS=!ARGS! --fix %%A"
for %%A in (%FIXBTEXT%) do set "ARGS=!ARGS! --fix-backup %%A"

echo.
call ".venv\Scripts\duty-roster.exe" generate -s "!SCHEDULE!" -c config\roster.yaml !ARGS!
if errorlevel 1 (
    echo.
    echo --------------------------------------------
    echo 確認事項があります。上の内容をご確認ください。
    echo 表は作成されています。
    echo --------------------------------------------
)
echo.
echo ダウンロード\待機表\ に保存されています。
echo.
pause
