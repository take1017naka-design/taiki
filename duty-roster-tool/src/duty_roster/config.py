"""設定ファイル(YAML)の読み込みと既定値。

ルールの閾値・優先順位・氏名などはすべてここで外出しにしてある。
コード側にハードコードした人名は無い。
"""

from __future__ import annotations

import copy
import datetime as dt
import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# 既定値。ユーザーのYAMLはこの辞書に対して再帰的にマージされる。
# ---------------------------------------------------------------------------
DEFAULTS: dict[str, Any] = {
    "members": [],
    "quota_by_month_length": {},
    "roles": {
        # この人が不在の日は dependents も待機不可（バックアップ不在のため）
        "backup_anchor": None,
        "backup_dependents": [],
        # この集団の待機が max_run 日を超えて連続してはいけない
        "consecutive_group": [],
        "consecutive_group_max_run": 2,
        # 1人あたり同じ週（日曜始まり）に入る回数の目安
        "max_per_week": 2,
        # この日数より短い間隔で同じ人が入るのを避ける（1=連日）
        "min_gap_days": 3,
        # 土日の待機対象者
        "weekend_pool": [],
        # 日曜は「この中から1人1回ずつ」
        "sunday_once_each": True,
        # 対象者全員が不在の日（日曜・祝日の一斉「公」など）は、
        # 不在を理由とする待機不可を解除する。解除しても赤字・黄色セル・
        # 土日プール・バックアップ役の条件は効いたまま。
        "all_absent_exception": True,
    },
    # 表記ゆれの読み替え（正規化後の文字列 -> 正規化後の文字列）
    "code_aliases": {"一/公": "―/公"},
    "plan_codes": {
        # 色に関わらず不在扱い（黒字でも不在は待機不可）
        "absent_always": ["公", "有", "夏", "リ", "出", "有/公"],
        # 赤字のときだけ不在扱いにしたい記号があればここへ
        "absent_if_red": [],
        # 祝日・日曜に限り「赤字でなければ待機可能」とする記号。
        # 祝日は全員が「公」になるため、これが無いと担当者を選べない。
        "holiday_relaxed": ["公"],
        # 赤字をどこまで「本人希望の不在」とみなすか。
        #   absence_codes: 不在表記（公・有・夏 など）の赤字だけ
        #   any          : 赤字のセルはすべて
        # 実際の勤務表では カテ・ABL の強調にも赤字が使われるため既定は absence_codes。
        "red_scope": "absence_codes",
    },
    "priority": {
        # 翌日の勤務内容をどの行から読むか: both / actual / plan
        # （実ファイルでは予・実の上下段に意味の差がないため既定は both）
        "duty_source": "both",
        # 月〜木: 翌日の勤務内容で優先順位を決める。上から順に適用。
        "mon_thu": [
            ["ME"],
            ["OHP", "内視"],
            ["災", "業", "労", "研修", "材料"],
            ["機"],
            ["OP", "アーム", ""],
        ],
        # 日曜: 翌日(月)の勤務内容
        "sun": [
            ["ME", "OHP", "内視", "機", "災", "業", "労", "研修", "材料"],
            ["OP", "アーム", ""],
        ],
        # 日曜は、翌日(月)がこれらの勤務（手術室）だけの人は待機不可。
        # "" は空白（記載なし＝手術室勤務）を表す。
        # ただし連休（翌日が祝日、または対象者全員が不在）のときはこの制限を外す。
        "sun_blocked_next_duties": ["OP", "アーム", ""],
        # 金曜: 翌日(土)に勤務がある人を優先、次点はそれ以外
        # 祝日は、その日に出勤している人を待機にする（いる場合）。
        # 祝日は多くが「公」になるため、実際に院内にいる人が担当する。
        "holiday_prefer_working": True,
        "fri_mode": "next_day_working",
        # 土曜: weekend_pool の在席者（優先順位なし）
        "sat_mode": "weekend_pool",
    },
    "weights": {
        # 優先順位(tier)ごとのコスト。index 0 が第1優先。
        "tier": [0, 60, 150, 240, 900],
        # どの優先順位にも当てはまらない人を充てた場合のコスト
        "fallback_tier": 4000,
        # 連日待機1回あたりのコスト（3.④以外は努力目標）。
        # sunday_prev_absent より大きくして、「連日になるくらいなら
        # 前日(土)不在の候補を使う」順序にしている。
        "consecutive": 1500,
        # 間隔が min_gap_days 未満（連日を除く＝中1日など）1件あたり
        "short_gap": 400,
        # 同じ週に max_per_week を超えて入る1回あたり
        "week_overload": 800,
        # 日曜に「前日(土)が不在」の人を充てる場合のコスト。
        # 日曜の優先順位の差（tier × sunday_tier_multiplier）より大きくして、
        # 「制限なしの候補がいるなら、優先順位が下でもそちらを使う」順序にしている。
        "sunday_prev_absent": 1300,
        # 祝日に、その日の出勤者がいるのに出勤していない人を充てる場合のコスト
        "holiday_not_working": 3000,
        # 日曜に「翌日(月)が手術室勤務（空白・OP・アーム）」の人を充てる場合のコスト。
        # 日曜の優先順位は翌日の勤務内容で決まるため、前日(土)不在より重い最後の手段。
        "sunday_next_operating_room": 2500,
        # 日曜の優先順位を重くする倍率。日曜は「1人1回ずつ」の総当たりで
        # 優先順位を満たす組み合わせを探すルールなので、平日側の都合で
        # 崩されないようにする。
        "sunday_tier_multiplier": 20,
        # ハード制約違反（本来ありえない）に付ける巨大コスト
        "ineligible": 1_000_000,
        "group_run": 1_000_000,
        # 土日祝の回数の偏り（1回のズレの2乗あたり）
        "holiday_fairness": 15,
    },
    "colors": {
        # 「濃い黄色」と判定する HSV 範囲（hueは度）
        "yellow_hue": [38, 70],
        "yellow_min_saturation": 0.35,
        "yellow_min_value": 0.60,
        # 赤字と判定する RGB 条件
        "red_min_r": 140,
        "red_max_g": 110,
        "red_max_b": 110,
    },
    # 日本の祝日を自動計算する。False にすると holidays に書いた日だけを使う。
    "holidays_auto": True,
    "holidays": [],
    # 予備待機表
    "backup_roster": {
        "enabled": True,
        # 待機が backup_dependents の日は、必ず backup_anchor が予備に入る
        "forced_anchor_for_dependents": True,
        # 待機がこの人の日は、予備にこの人たちを入れない（待機者 -> 予備不可の一覧）
        "forbidden_pairs": {},
        # 土日・祝日は「バックアップ役が不在なら依存2名も不可」を適用しない。
        # 予備は土日祝も8名全員が対象。
        "anchor_rule_on_weekends": False,
        # 回数の目標を見ない人（バックアップ役は自動確定の日が多いため）
        "quota_ignore": [],
        # 回数の目標を優先する人。優先順位のはしごより回数を上に置く。
        "quota_priority": [],
        # 予備の回数は待機表の目標ではなく、quota_ignore を除く全員で均等にする
        "even_quota": True,
        # 連続日数を見ない人（自動確定の日が多く、連続を避けようがないため）。
        # 上限では止めないが、consecutive_report_threshold 日以上になったら報告する。
        "consecutive_ignore": [],
        "consecutive_report_threshold": 4,
        # 日曜・祝日の予備を年間で均等にする。ここに書いた人は対象外。
        "holiday_fairness_ignore": [],
        # 予備では、本人希望の不可日（赤字・黄色セル）以外はすべて可とする人。
        # 不在（公・有・夏 など）も日曜の追加条件も適用しない。
        "always_available": [],
        # 土日は予備に入れない人（祝日と重なる日は下の holiday_consult で扱う）
        "weekend_excluded": [],
        # 祝日に予備へ入れたら「要相談」として確認事項に出す人
        "holiday_consult": [],
        # 待機＋予備を合算した連続日数の上限
        "max_run_default": 2,
        "max_run_exceptions": {},
        "weights": {
            "quota_deviation": 250,    # 目標回数からのズレ（2乗あたり）
            # even_quota のときの、平均からのズレ（2乗あたり）
            "even_quota_deviation": 3000,
            # 回数を見ない人（バックアップ役）に、自動確定以外の日を充てる1日あたり。
            # 何もしないと余った日が集まってしまうため。
            "ignored_extra_day": 2500,
            # quota_priority の人のズレ（2乗あたり）。最後の段のコストより重くして、
            # 翌日が手術室の日でも回数を合わせにいく。
            "quota_deviation_priority": 40000,
            # 合算して連日になる1件あたり。均等配分と釣り合う重さにしてある。
            "consecutive": 4000,
            "holiday_fairness": 400,  # 日曜・祝日の予備の年間の偏り（2乗あたり）
            "holiday_consult": 2000,  # 祝日に holiday_consult の人を充てる
            "sunday_repeat": 6000,    # 日曜の予備に同じ人を月内で2回以上使う
            "violation": 1_000_000,   # ハード制約違反
        },
        # 「第4優先までで組めなければ翌日空白も可」というはしごを守るため、
        # 最後の段（OP・アーム・空白）と該当なしだけを重くする倍率。
        # 第1〜第4優先どうしの差は待機表と同じ重みのままにして、
        # 連日回避などのソフト条件と釣り合わせる。
        "last_resort_multiplier": 40,
        # 日曜の予備も月内で1人1回ずつ（無理なら重いコストで許容する）
        "sunday_once_each": True,
        "search": {"restarts": 12, "iterations": 4000},
    },
    # 月をまたいだ実績の記録（日曜・祝日の予備を年間で均等にするために使う）
    "history": {"enabled": True, "path": "config/history.json"},
    # 先に決まっている担当。ルールに関係なくこのとおり入れる。
    #   fixed_assignments:
    #     2026-10-05: 坂本
    "fixed_assignments": {},
    # 勤務表から読み取れない事情を手で足す。氏名 -> 日付（と理由）のリスト。
    #   manual_unavailable:
    #     坂本: ["2026-09-20"]
    #     一戸: [{date: "2026-09-13", reason: "研究会"}]
    "manual_unavailable": {},
    "excel": {
        "sheet": None,          # None なら先頭シート
        "header_row": None,     # None なら自動検出（1〜31が並ぶ行）
        "name_column": None,    # None なら自動検出（氏名が並ぶ列）
        "kind_column": None,    # None なら自動検出（予/実 が並ぶ列）
        "plan_label": "予",
        "actual_label": "実",
        "max_scan_rows": 40,
        "max_scan_cols": 20,
    },
    "search": {
        "seed": 20260101,
        "restarts": 60,
        "local_search_iterations": 6000,
        "sunday_candidates": 16,
    },
    "output": {
        # 保存先フォルダ。~ や環境変数も使える。
        # 既定はダウンロードフォルダの中の「待機表」フォルダ（無ければ作る）。
        #   共有フォルダの例: "//server/share/臨床工学科/待機表"
        #   デスクトップの例: "~/Desktop/待機表"
        "directory": "~/Downloads/待機表",
        # ファイル名。{year} と {month} が使える。
        "filename": "待機表_{year}{month:02d}.xlsx",
        "backup_filename": "予備待機表_{year}{month:02d}.xlsx",
        "personal_filename": "個人別待機表_{year}{month:02d}.xlsx",
        # 個人別の表で使う文字色（待機＝赤字、予備＝黒字）
        "personal_duty_color": "FFFF0000",
        "personal_backup_color": "FF000000",
        "weekday_font_color": "FF000000",
        "saturday_font_color": "FF0070C0",
        "sunday_font_color": "FFFF0000",
        # 印刷設定。既定は A4 横・幅を1ページに収める。
        "paper_size": 9,          # 9 = A4
        "paper_landscape": True,
        "page_margin_inch": 0.4,
        # 用紙の中央に配置する（縦方向は1ページに収まるシートのみ）
        "center_horizontally": True,
        "center_vertically": True,
        # 担当ごとの待機日数を出す位置（カレンダーの右横）
        "counts_column": 9,
        "counts_row": 3,
        # カレンダーのセルの大きさ。A4横1ページいっぱいになるようにしてある。
        # （印刷可能領域 10.89 x 7.47 インチ に対して 10.77 x 6.94 インチ）
        "calendar_column_width": 17.0,
        "calendar_date_row_height": 36.0,
        "calendar_name_row_height": 36.0,
        # 文字の大きさ
        "title_font_size": 18,
        "weekday_font_size": 14,
        "date_font_size": 14,
        "name_font_size": 18,
        "counts_font_size": 12,
        # カレンダーのセルの塗り。日曜・祝日は同じ色、土曜は薄い青。
        "holiday_fill": "FFFDE9E9",
        "saturday_fill": "FFDEEBF7",
        "weekday_fill": None,
    },
}

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


@dataclass(frozen=True)
class Member:
    name: str
    note: str = ""


@dataclass
class Config:
    """YAMLの内容をそのまま保持し、型付きのアクセサを提供する。"""

    raw: dict[str, Any]
    path: Path | None = None

    # -- 基本情報 ----------------------------------------------------------
    @property
    def members(self) -> list[Member]:
        out: list[Member] = []
        for item in self.raw["members"]:
            if isinstance(item, str):
                out.append(Member(name=item.strip()))
            else:
                out.append(Member(name=str(item["name"]).strip(), note=str(item.get("note", ""))))
        return out

    @property
    def member_names(self) -> list[str]:
        return [m.name for m in self.members]

    def quota(self, days_in_month: int) -> dict[str, int]:
        table = self.raw["quota_by_month_length"]
        key = days_in_month if days_in_month in table else str(days_in_month)
        if key not in table:
            raise ConfigError(
                f"quota_by_month_length に {days_in_month} 日の月の設定がありません。"
            )
        return {str(k): int(v) for k, v in table[key].items()}

    # -- 役割 --------------------------------------------------------------
    @property
    def backup_anchor(self) -> str | None:
        v = self.raw["roles"].get("backup_anchor")
        return str(v) if v else None

    @property
    def backup_dependents(self) -> list[str]:
        return [str(x) for x in self.raw["roles"].get("backup_dependents", [])]

    @property
    def consecutive_group(self) -> list[str]:
        return [str(x) for x in self.raw["roles"].get("consecutive_group", [])]

    @property
    def consecutive_group_max_run(self) -> int:
        return int(self.raw["roles"].get("consecutive_group_max_run", 2))

    @property
    def max_per_week(self) -> int:
        return int(self.raw["roles"].get("max_per_week", 0))

    @property
    def min_gap_days(self) -> int:
        return int(self.raw["roles"].get("min_gap_days", 1))

    @property
    def weekend_pool(self) -> list[str]:
        return [str(x) for x in self.raw["roles"].get("weekend_pool", [])]

    @property
    def sunday_once_each(self) -> bool:
        return bool(self.raw["roles"].get("sunday_once_each", True))

    # -- 勤務記号 ----------------------------------------------------------
    @property
    def code_aliases(self) -> dict[str, str]:
        return {
            normalize_code(k): normalize_code(v)
            for k, v in (self.raw.get("code_aliases") or {}).items()
        }

    @property
    def holiday_relaxed(self) -> set[str]:
        return {normalize_code(c) for c in self.raw["plan_codes"].get("holiday_relaxed", [])}

    @property
    def absent_always(self) -> set[str]:
        return {normalize_code(c) for c in self.raw["plan_codes"]["absent_always"]}

    @property
    def absent_if_red(self) -> set[str]:
        return {normalize_code(c) for c in self.raw["plan_codes"]["absent_if_red"]}

    # -- 祝日 --------------------------------------------------------------
    @property
    def holidays(self) -> set[dt.date]:
        out: set[dt.date] = set()
        for item in self.raw.get("holidays") or []:
            if isinstance(item, dt.datetime):
                out.add(item.date())
            elif isinstance(item, dt.date):
                out.add(item)
            else:
                out.add(dt.date.fromisoformat(str(item).strip()))
        return out

    # -- セクション --------------------------------------------------------
    @property
    def holidays_auto(self) -> bool:
        return bool(self.raw.get("holidays_auto", True))

    # -- 予備待機表 --------------------------------------------------------
    @property
    def backup(self) -> dict[str, Any]:
        return self.raw["backup_roster"]

    @property
    def backup_enabled(self) -> bool:
        return bool(self.backup.get("enabled", True))

    @property
    def backup_forbidden_pairs(self) -> dict[str, set[str]]:
        return {
            str(k): {str(v) for v in (values or [])}
            for k, values in (self.backup.get("forbidden_pairs") or {}).items()
        }

    @property
    def backup_quota_ignore(self) -> set[str]:
        return {str(n) for n in (self.backup.get("quota_ignore") or [])}

    @property
    def backup_consecutive_ignore(self) -> set[str]:
        return {str(n) for n in (self.backup.get("consecutive_ignore") or [])}

    @property
    def backup_even_quota(self) -> bool:
        return bool(self.backup.get("even_quota", True))

    @property
    def backup_quota_priority(self) -> set[str]:
        return {str(n) for n in (self.backup.get("quota_priority") or [])}

    @property
    def backup_always_available(self) -> set[str]:
        return {str(n) for n in (self.backup.get("always_available") or [])}

    @property
    def backup_weekend_excluded(self) -> set[str]:
        return {str(n) for n in (self.backup.get("weekend_excluded") or [])}

    @property
    def backup_holiday_consult(self) -> set[str]:
        return {str(n) for n in (self.backup.get("holiday_consult") or [])}

    @property
    def backup_consecutive_report_threshold(self) -> int:
        return int(self.backup.get("consecutive_report_threshold", 4))

    @property
    def backup_holiday_fairness_ignore(self) -> set[str]:
        return {str(n) for n in (self.backup.get("holiday_fairness_ignore") or [])}

    @property
    def history_enabled(self) -> bool:
        return bool((self.raw.get("history") or {}).get("enabled", True))

    @property
    def history_path(self) -> Path:
        raw = (self.raw.get("history") or {}).get("path") or "config/history.json"
        path = Path(os.path.expandvars(str(raw))).expanduser()
        if not path.is_absolute() and self.path is not None:
            path = self.path.parent / path.name
        return path

    @property
    def backup_anchor_rule_on_weekends(self) -> bool:
        """土日祝も「バックアップ役の不在」を予備の可否に反映するか。"""
        raw = self.backup
        if "anchor_rule_on_weekends" in raw:
            return bool(raw["anchor_rule_on_weekends"])
        return bool(raw.get("anchor_rule_on_holidays", False))

    def backup_max_run(self, name: str) -> int:
        exceptions = self.backup.get("max_run_exceptions") or {}
        return int(exceptions.get(name, self.backup.get("max_run_default", 2)))

    def fixed_backup_assignments(self, year: int, month: int) -> dict[dt.date, str]:
        out: dict[dt.date, str] = {}
        for raw_day, name in (self.backup.get("fixed_assignments") or {}).items():
            day = parse_day(raw_day, year, month)
            if day.year == year and day.month == month:
                out[day] = str(name).strip()
        return out

    def fixed_assignments(self, year: int, month: int) -> dict[dt.date, str]:
        """先に決まっている担当（対象月のぶんだけ）。"""
        out: dict[dt.date, str] = {}
        for raw_day, name in (self.raw.get("fixed_assignments") or {}).items():
            day = parse_day(raw_day, year, month)
            if day.year == year and day.month == month:
                out[day] = str(name).strip()
        return out

    @property
    def manual_unavailable(self) -> dict[str, dict[dt.date, str]]:
        out: dict[str, dict[dt.date, str]] = {}
        for name, entries in (self.raw.get("manual_unavailable") or {}).items():
            days: dict[dt.date, str] = {}
            for entry in entries or []:
                if isinstance(entry, dict):
                    raw_date, reason = entry.get("date"), str(entry.get("reason", "手動指定"))
                else:
                    raw_date, reason = entry, "手動指定"
                if isinstance(raw_date, dt.datetime):
                    day = raw_date.date()
                elif isinstance(raw_date, dt.date):
                    day = raw_date
                else:
                    day = dt.date.fromisoformat(str(raw_date).strip())
                days[day] = reason
            out[str(name)] = days
        return out

    @property
    def priority(self) -> dict[str, Any]:
        return self.raw["priority"]

    @property
    def sun_blocked_next_duties(self) -> set[str]:
        return {
            normalize_code(c)
            for c in self.raw["priority"].get("sun_blocked_next_duties", [])
        }

    @property
    def weights(self) -> dict[str, Any]:
        return self.raw["weights"]

    @property
    def colors(self) -> dict[str, Any]:
        return self.raw["colors"]

    @property
    def excel(self) -> dict[str, Any]:
        return self.raw["excel"]

    @property
    def search(self) -> dict[str, Any]:
        return self.raw["search"]

    @property
    def output(self) -> dict[str, Any]:
        return self.raw["output"]

    def output_path(self, year: int, month: int) -> Path:
        """設定から既定の出力先を組み立てる。"""
        out = self.raw["output"]
        directory = os.path.expandvars(str(out.get("directory") or "out"))
        filename = str(out.get("filename") or "待機表_{year}{month:02d}.xlsx")
        return (Path(directory).expanduser() / filename.format(year=year, month=month)).resolve()

    def _named_output(self, key: str, default: str, year: int, month: int) -> Path:
        out = self.raw["output"]
        directory = os.path.expandvars(str(out.get("directory") or "out"))
        filename = str(out.get(key) or default)
        return (Path(directory).expanduser() / filename.format(year=year, month=month)).resolve()

    def backup_output_path(self, year: int, month: int) -> Path:
        return self._named_output(
            "backup_filename", "予備待機表_{year}{month:02d}.xlsx", year, month
        )

    def personal_output_path(self, year: int, month: int) -> Path:
        return self._named_output(
            "personal_filename", "個人別待機表_{year}{month:02d}.xlsx", year, month
        )


class ConfigError(Exception):
    """設定内容の不備。"""


# 「日勤」を表す横棒の異体字。実ファイルでは ￣(U+FFE3) が使われている。
_DASH_CHARS = "\uffe3\u203e\u00af\u2015\u2014\u2013\u2010\u002d\uff0d\u2500\u0304"
DASH = "―"


def normalize_code(value: Any) -> str:
    """勤務記号・氏名の表記ゆれを吸収する。

    * 全角英数字・半角カナを NFKC で統一（ＭＥ→ME、ｶﾃ→カテ、／→/）
    * 「日勤」の横棒（￣ ‾ ¯ ─ - など）をすべて ― に統一
    * 前後の空白を落とし、連続空白を1つにまとめ、ASCII は大文字化
    """
    if value is None:
        return ""
    text = str(value)
    # NFKC で ￣ が「空白＋結合マクロン」に分解されてしまうため、先に潰す。
    text = "".join(DASH if ch in _DASH_CHARS else ch for ch in text)
    text = unicodedata.normalize("NFKC", text)
    text = "".join(DASH if ch in _DASH_CHARS else ch for ch in text)
    text = text.replace("\u3000", " ")
    text = " ".join(text.split())
    return text.upper()


def normalize_name(value: Any) -> str:
    """氏名の比較用。空白をすべて除去する（「担当A　太郎」→「担当A太郎」）。"""
    return normalize_code(value).replace(" ", "")


def parse_day(value: Any, year: int, month: int) -> dt.date:
    """日付を解釈する。「5」のような日だけの指定は対象月の日付とみなす。"""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    if text.isdigit():
        return dt.date(year, month, int(text))
    return dt.date.fromisoformat(text)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """base を override で再帰的に上書きした新しい辞書を返す。"""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"設定ファイルが見つかりません: {path}")
    with path.open(encoding="utf-8") as fh:
        user = yaml.safe_load(fh) or {}
    if not isinstance(user, dict):
        raise ConfigError(f"設定ファイルの形式が不正です: {path}")
    cfg = Config(raw=deep_merge(DEFAULTS, user), path=path)
    validate(cfg)
    return cfg


def validate(cfg: Config) -> None:
    names = cfg.member_names
    if not names:
        raise ConfigError("members が空です。対象者を設定してください。")
    if len(set(names)) != len(names):
        raise ConfigError("members に重複した氏名があります。")

    known = set(names)

    def check(label: str, values: list[str]) -> None:
        unknown = [v for v in values if v not in known]
        if unknown:
            raise ConfigError(f"{label} に members へ未登録の氏名があります: {unknown}")

    if cfg.backup_anchor:
        check("roles.backup_anchor", [cfg.backup_anchor])
    check("roles.backup_dependents", cfg.backup_dependents)
    check("roles.consecutive_group", cfg.consecutive_group)
    check("roles.weekend_pool", cfg.weekend_pool)
    check("manual_unavailable", list(cfg.manual_unavailable))
    pairs = cfg.backup_forbidden_pairs
    check("backup_roster.forbidden_pairs", list(pairs))
    for primary, blocked in pairs.items():
        check(f"backup_roster.forbidden_pairs[{primary}]", sorted(blocked))
    check("backup_roster.max_run_exceptions", list(cfg.backup.get("max_run_exceptions") or {}))
    check("backup_roster.quota_ignore", sorted(cfg.backup_quota_ignore))
    check("backup_roster.quota_priority", sorted(cfg.backup_quota_priority))
    check("backup_roster.consecutive_ignore", sorted(cfg.backup_consecutive_ignore))
    check(
        "backup_roster.holiday_fairness_ignore",
        sorted(cfg.backup_holiday_fairness_ignore),
    )
    check("backup_roster.always_available", sorted(cfg.backup_always_available))
    check("backup_roster.weekend_excluded", sorted(cfg.backup_weekend_excluded))
    check("backup_roster.holiday_consult", sorted(cfg.backup_holiday_consult))

    table = cfg.raw["quota_by_month_length"]
    if not table:
        raise ConfigError("quota_by_month_length が空です。月の日数ごとの回数を設定してください。")
    for length, quota in table.items():
        length_int = int(length)
        check(f"quota_by_month_length[{length}]", [str(k) for k in quota])
        total = sum(int(v) for v in quota.values())
        if total != length_int:
            raise ConfigError(
                f"quota_by_month_length[{length}] の合計が {total} 回で、"
                f"月の日数 {length_int} と一致しません。"
            )
