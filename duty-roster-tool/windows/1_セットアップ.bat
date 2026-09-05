@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

echo ============================================
echo  カテ待機表ツール セットアップ
echo ============================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo [エラー] Python が見つかりません。
        echo.
        echo   https://www.python.org/downloads/windows/ から
        echo   Python 3.10 以降をインストールしてください。
        echo   インストール時に「Add python.exe to PATH」に必ずチェックを入れてください。
        echo.
        pause
        exit /b 1
    )
)

echo Python を確認しました。
%PY% --version
echo.

echo 必要な部品を入れています（初回は数分かかります）...
if not exist ".venv" (
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [エラー] 準備に失敗しました。
        pause
        exit /b 1
    )
)
call ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
call ".venv\Scripts\python.exe" -m pip install --quiet -e .
if errorlevel 1 (
    echo [エラー] 部品の取得に失敗しました。ネットワークをご確認ください。
    pause
    exit /b 1
)

echo.
echo セットアップが終わりました。
echo.
if exist "config\roster.yaml" (
    echo 設定ファイルは作成済みです: config\roster.yaml
    echo そのまま「3_待機表を作る.bat」をお使いください。
) else (
    echo 次に「2_設定ファイルを作る.bat」を実行してください。
)
echo.
pause
