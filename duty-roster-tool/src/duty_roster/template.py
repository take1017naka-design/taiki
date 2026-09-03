"""設定ファイルのひな型生成。

氏名はリポジトリに置かず、勤務表から取り込んで手元の設定ファイルに書き出す。
ルールの「形」（誰が何番目の役割か）だけをここに持たせている。
"""

from __future__ import annotations

# 8名運用のときの既定の並び（勤務割当表の記載順を想定）
#   1人目: バックアップ役（この人が不在だと 7・8人目も待機不可）
#   2〜6人目: 土日の担当プール（日曜は1人1回ずつ）
#   7・8人目: バックアップ役に依存する2名
DEFAULT_QUOTA_BY_INDEX = {
    31: [4, 5, 4, 4, 4, 4, 3, 3],
    30: [3, 5, 4, 4, 4, 4, 3, 3],
    29: [4, 5, 4, 4, 3, 3, 3, 3],
    28: [3, 5, 4, 4, 3, 3, 3, 3],
}
ANCHOR_INDEX = 0
DEPENDENT_INDEXES = [6, 7]
WEEKEND_POOL_INDEXES = [1, 2, 3, 4, 5]


def _yaml_list(names: list[str]) -> str:
    return "[" + ", ".join(names) + "]"


def build_config_text(names: list[str]) -> str:
    """氏名リストから設定ファイル本文を作る。"""
    n = len(names)
    positional = n == len(DEFAULT_QUOTA_BY_INDEX[31])

    lines: list[str] = [
        "# カテ待機表 自動作成ツール 設定ファイル",
        "# duty-roster-tool init-config で生成。氏名を含むため共有・コミットしないこと。",
        "",
        "members:",
    ]
    lines += [f"  - {name}" for name in names]
    lines.append("")

    lines.append("# 月の日数ごとの待機回数（合計＝月の日数になるように）")
    lines.append("quota_by_month_length:")
    for length, quota in DEFAULT_QUOTA_BY_INDEX.items():
        lines.append(f"  {length}:")
        if positional:
            for name, count in zip(names, quota):
                lines.append(f"    {name}: {count}")
        else:
            base, extra = divmod(length, n)
            for i, name in enumerate(names):
                lines.append(f"    {name}: {base + (1 if i < extra else 0)}  # TODO 実際の回数に修正")
    lines.append("")

    anchor = names[ANCHOR_INDEX] if positional else "  # TODO"
    dependents = [names[i] for i in DEPENDENT_INDEXES] if positional else []
    weekend = [names[i] for i in WEEKEND_POOL_INDEXES] if positional else []
    group = ([names[ANCHOR_INDEX]] + dependents) if positional else []

    lines += [
        "roles:",
        "  # この人が不在の日は backup_dependents も待機不可（バックアップに入れないため）",
        f"  backup_anchor: {anchor if positional else ''}" + ("" if positional else "  # TODO"),
        f"  backup_dependents: {_yaml_list(dependents)}" + ("" if positional else "  # TODO"),
        "  # この3名の待機が3日以上連続しないようにする",
        f"  consecutive_group: {_yaml_list(group)}" + ("" if positional else "  # TODO"),
        "  consecutive_group_max_run: 2",
        "  # 土日の担当対象者",
        f"  weekend_pool: {_yaml_list(weekend)}" + ("" if positional else "  # TODO"),
        "  # 日曜は上記5名から1人1回ずつ",
        "  sunday_once_each: true",
        "",
        "# 祝日（カレンダーの日付を赤字にする。勤務表の一斉「公」は黒字なら待機可能）",
        "holidays: []",
        "",
        "# 以下は既定値のままで動く。必要に応じて上書きすること。",
        "# priority / plan_codes / weights / colors / excel / search は",
        "# duty_roster/config.py の DEFAULTS を参照。",
        "",
    ]
    return "\n".join(lines)
