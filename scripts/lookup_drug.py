#!/usr/bin/env python3
"""PCI時確認薬剤辞書の検索ツール。

商品名または一般名(部分一致)で data/pci_drug_dictionary.json を検索し、
該当する薬剤情報を表示する。該当がなければ「該当なし」と表示する。

使い方:
    python3 scripts/lookup_drug.py <薬剤名>
    python3 scripts/lookup_drug.py            # 対話モード
"""

import json
import sys
import unicodedata
from pathlib import Path

DICT_PATH = Path(__file__).resolve().parent.parent / "data" / "pci_drug_dictionary.json"


def normalize(text: str) -> str:
    """全角/半角・大小文字・前後空白の揺れを吸収する。"""
    return unicodedata.normalize("NFKC", text).strip().lower()


def load_drugs() -> list[dict]:
    with DICT_PATH.open(encoding="utf-8") as f:
        return json.load(f)["drugs"]


def search(query: str, drugs: list[dict]) -> list[dict]:
    q = normalize(query)
    if not q:
        return []

    matches = []
    for drug in drugs:
        names = [drug["generic_name"], *drug["brand_names"], *drug.get("components", [])]
        if any(q in normalize(name) for name in names):
            matches.append(drug)
    return matches


def format_drug(drug: dict) -> str:
    lines = [
        f"一般名: {drug['generic_name']}",
        f"商品名: {', '.join(drug['brand_names'])}",
        f"分類: {drug['category']} / {drug['subcategory']}",
    ]
    if drug.get("is_combination"):
        lines.append(f"配合成分: {', '.join(drug['components'])}")
    bucket = drug.get("pci_check_bucket") or []
    lines.append(f"該当区分: {', '.join(bucket) if bucket else '該当なし(区分未設定)'}")
    return "\n".join(lines)


def lookup_and_print(query: str, drugs: list[dict]) -> None:
    matches = search(query, drugs)
    if not matches:
        print("該当なし")
        return
    print("\n---\n".join(format_drug(m) for m in matches))


def main() -> None:
    drugs = load_drugs()

    if len(sys.argv) > 1:
        lookup_and_print(" ".join(sys.argv[1:]), drugs)
        return

    print("薬剤名(商品名または一般名)を入力してください。終了は Ctrl+D または 'exit'。")
    while True:
        try:
            query = input("> ")
        except EOFError:
            break
        if query.strip().lower() == "exit":
            break
        lookup_and_print(query, drugs)


if __name__ == "__main__":
    main()
