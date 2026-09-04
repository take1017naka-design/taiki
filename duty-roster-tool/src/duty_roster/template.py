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
# 予備待機: 待機が3人目の日は、依存①を予備にしない
BACKUP_FORBIDDEN = {2: [6]}
# 待機＋予備を合算した連続日数の上限を緩める人（1人目・2人目は3日まで）
BACKUP_LONG_RUN_INDEXES = [0, 1]


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

    if positional:
        forbidden = {
            names[primary]: [names[i] for i in blocked]
            for primary, blocked in BACKUP_FORBIDDEN.items()
        }
        long_run = {names[i]: 3 for i in BACKUP_LONG_RUN_INDEXES}
    else:
        forbidden, long_run = {}, {}

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
        "# 予備待機表",
        "backup_roster:",
        "  enabled: true",
        "  # 待機が backup_dependents の日は、必ず backup_anchor が予備に入る",
        "  forced_anchor_for_dependents: true",
        "  # 土日・祝日は「バックアップ役が不在なら依存2名も不可」を適用しない",
        "  anchor_rule_on_weekends: false",
        "  # 予備の回数は目標を見ない人（自動確定の日が多いバックアップ役）",
        f"  quota_ignore: {_yaml_list([names[ANCHOR_INDEX]] if positional else [])}",
        "  # 予備の連続日数を見ない人（自動確定の日が多く、避けようがないため）",
        f"  consecutive_ignore: {_yaml_list([names[ANCHOR_INDEX]] if positional else [])}",
        "  # 上限では止めないが、この日数以上の連続になったら確認事項に出す",
        "  consecutive_report_threshold: 4",
        "  # 日曜・祝日の予備を年間で均等にする。ここに書いた人は対象外。",
        f"  holiday_fairness_ignore: {_yaml_list([names[ANCHOR_INDEX]] if positional else [])}",
        "  # 待機がこの人の日は、予備にこの人たちを入れない",
        "  forbidden_pairs:"
        + ("" if forbidden else " {}"),
    ]
    for primary, blocked in forbidden.items():
        lines.append(f"    {primary}: {_yaml_list(blocked)}")
    lines += [
        "  # 待機＋予備を合算した連続日数の上限（既定2日）",
        "  max_run_default: 2",
        "  max_run_exceptions:" + ("" if long_run else " {}"),
    ]
    for name, value in long_run.items():
        lines.append(f"    {name}: {value}")
    lines += [
        "",
        "# 待機表の保存先（無ければ自動で作る）",
        "output:",
        '  directory: "~/Downloads/待機表"',
        '  filename: "待機表_{year}{month:02d}.xlsx"',
        "",
        "# 祝日。日付を赤字にし、その日の「公」は赤字でなければ待機可能として扱う。",
        "# 日本の祝日は自動計算するので通常は空のままでよい。",
        "holidays: []",
        "",
        "# 以下は既定値のままで動く。必要に応じて上書きすること。",
        "# priority / plan_codes / weights / colors / excel / search は",
        "# duty_roster/config.py の DEFAULTS を参照。",
        "",
    ]
    return "\n".join(lines)
