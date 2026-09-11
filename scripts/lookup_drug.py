#!/usr/bin/env python3
"""PCI/EVT時確認薬剤辞書の検索ツール。

商品名または一般名(部分一致)で data/pci_drug_dictionary.json を検索し、
該当する薬剤情報を表示する。該当がなければ「該当なし」と表示する。
辞書はPCI/EVT共通だが、該当区分(pci_check_bucket / evt_check_bucket)は
モードごとに異なる。

使い方:
    python3 scripts/lookup_drug.py <薬剤名> [--mode pci|evt]
    python3 scripts/lookup_drug.py [--mode pci|evt]   # 対話モード(既定はpci)
"""

import json
import sys
import unicodedata
from pathlib import Path

DICT_PATH = Path(__file__).resolve().parent.parent / "data" / "pci_drug_dictionary.json"
BUCKET_FIELD = {"pci": "pci_check_bucket", "evt": "evt_check_bucket"}


def normalize(text: str) -> str:
    """全角/半角・大小文字・前後空白の揺れを吸収する。"""
    return unicodedata.normalize("NFKC", text).strip().lower()


def load_drugs() -> list[dict]:
    with DICT_PATH.open(encoding="utf-8") as f:
        return json.load(f)["drugs"]


def search(query: str, drugs: list[dict], mode: str) -> list[dict]:
    q = normalize(query)
    if not q:
        return []

    bucket_field = BUCKET_FIELD[mode]
    matches = []
    for drug in drugs:
        if not drug.get(bucket_field):
            continue
        names = [drug["generic_name"], *drug["brand_names"], *drug.get("components", [])]
        if any(q in normalize(name) for name in names):
            matches.append(drug)
    return matches


def format_drug(drug: dict, mode: str) -> str:
    lines = [
        f"一般名: {drug['generic_name']}",
        f"商品名: {', '.join(drug['brand_names'])}",
        f"分類: {drug['category']} / {drug['subcategory']}",
    ]
    if drug.get("is_combination"):
        lines.append(f"配合成分: {', '.join(drug['components'])}")
    bucket = drug.get(BUCKET_FIELD[mode]) or []
    lines.append(f"該当区分({mode.upper()}): {', '.join(bucket)}")
    return "\n".join(lines)


def lookup_and_print(query: str, drugs: list[dict], mode: str) -> None:
    matches = search(query, drugs, mode)
    if not matches:
        print("該当なし")
        return
    print("\n---\n".join(format_drug(m, mode) for m in matches))


def parse_args(argv: list[str]) -> tuple[str, str]:
    mode = "pci"
    terms = []
    i = 0
    while i < len(argv):
        if argv[i] == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1]
            i += 2
        else:
            terms.append(argv[i])
            i += 1
    if mode not in BUCKET_FIELD:
        raise SystemExit(f"--mode は pci か evt を指定してください(指定値: {mode})")
    return " ".join(terms), mode


def main() -> None:
    drugs = load_drugs()
    query, mode = parse_args(sys.argv[1:])

    if query:
        lookup_and_print(query, drugs, mode)
        return

    print(f"[{mode.upper()}モード] 薬剤名(商品名または一般名)を入力してください。終了は Ctrl+D または 'exit'。")
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line.strip().lower() == "exit":
            break
        lookup_and_print(line, drugs, mode)


if __name__ == "__main__":
    main()
