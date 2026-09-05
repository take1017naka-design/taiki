#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
set -u

if [ ! -x .venv/bin/duty-roster ]; then
    echo "[エラー] 先に「セットアップ.command」を実行してください。"
    read -r -p "Enter キーで閉じます " _
    exit 1
fi
if [ ! -f config/roster.yaml ]; then
    echo "[エラー] 先に「設定ファイルを作る.command」を実行してください。"
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

echo
echo "先に決めておく担当があれば入力してください。無ければ Enter だけ。"
read -r -p "待機の指定（例 5=担当B 12=担当C）: " FIXTEXT
read -r -p "予備の指定（例 5=担当C）: " FIXBTEXT

ARGS=()
for item in $FIXTEXT; do ARGS+=(--fix "$item"); done
for item in $FIXBTEXT; do ARGS+=(--fix-backup "$item"); done

echo
./.venv/bin/duty-roster generate -s "$SCHEDULE" -c config/roster.yaml "${ARGS[@]}"
echo
echo "ダウンロード/待機表/ に保存されています。"
read -r -p "Enter キーで閉じます " _
