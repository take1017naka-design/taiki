#!/bin/bash
# Mac 用。ダブルクリックで実行できます。
cd "$(dirname "$0")/.." || exit 1
set -u

echo "============================================"
echo " カテ待機表ツール セットアップ"
echo "============================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "[エラー] Python が見つかりません。"
    echo "  https://www.python.org/downloads/ から Python 3.10 以降を入れてください。"
    read -r -p "Enter キーで閉じます " _
    exit 1
fi
python3 --version

echo
echo "必要な部品を入れています（初回は数分かかります）..."
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/python -m pip install --quiet --upgrade pip
if ! ./.venv/bin/python -m pip install --quiet -e .; then
    echo "[エラー] 部品の取得に失敗しました。ネットワークをご確認ください。"
    read -r -p "Enter キーで閉じます " _
    exit 1
fi

echo
echo "セットアップが終わりました。"
if [ -f config/roster.yaml ]; then
    echo "設定ファイルは作成済みです。「待機表を作る.command」をお使いください。"
else
    echo "次に「設定ファイルを作る.command」を実行してください。"
fi
read -r -p "Enter キーで閉じます " _
