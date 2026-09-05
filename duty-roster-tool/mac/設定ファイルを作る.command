#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
set -u

if [ ! -x .venv/bin/duty-roster ]; then
    echo "[エラー] 先に「セットアップ.command」を実行してください。"
    read -r -p "Enter キーで閉じます " _
    exit 1
fi

echo "勤務割当表の Excel を、このウィンドウにドラッグして Enter を押してください。"
read -r -p "勤務表: " SCHEDULE
SCHEDULE="${SCHEDULE%\"}"; SCHEDULE="${SCHEDULE#\"}"
SCHEDULE="${SCHEDULE//\\ / }"
if [ ! -f "$SCHEDULE" ]; then
    echo "[エラー] ファイルが見つかりません: $SCHEDULE"
    read -r -p "Enter キーで閉じます " _
    exit 1
fi

FORCE=""
if [ -f config/roster.yaml ]; then
    read -r -p "すでに設定ファイルがあります。上書きしますか？ (y/n): " ANS
    [ "$ANS" = "y" ] || { echo "やめました。"; read -r -p "Enter キーで閉じます " _; exit 0; }
    FORCE="--force"
fi

./.venv/bin/duty-roster init-config -s "$SCHEDULE" -o config/roster.yaml $FORCE
echo
echo "config/roster.yaml ができました。氏名が入るので共有しないでください。"
read -r -p "Enter キーで閉じます " _
