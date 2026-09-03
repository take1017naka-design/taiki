"""設定ファイル(YAML)の読み込みと既定値。

ルールの閾値・優先順位・氏名などはすべてここで外出しにしてある。
コード側にハードコードした人名は無い。
"""

from __future__ import annotations

import copy
import datetime as dt
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
        # 月〜木: 翌日の「実」欄で優先順位を決める。上から順に適用。
        "mon_thu": [["ME"], ["OHP", "内視"], ["機"], ["OP", "アーム", ""]],
        # 日曜: 翌日(月)の「実」欄
        "sun": [["ME", "OHP", "内視", "機"], ["OP", "アーム", ""]],
        # 金曜: 翌日(土)に勤務がある人を優先、次点はそれ以外
        "fri_mode": "next_day_working",
        # 土曜: weekend_pool の在席者（優先順位なし）
        "sat_mode": "weekend_pool",
    },
    "weights": {
        # 優先順位(tier)ごとのコスト。index 0 が第1優先。
        "tier": [0, 60, 240, 900],
        # どの優先順位にも当てはまらない人を充てた場合のコスト
        "fallback_tier": 4000,
        # 連日待機1回あたりのコスト（3.④以外は努力目標）
        "consecutive": 120,
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
        "weekday_font_color": "FF000000",
        "saturday_font_color": "FF0070C0",
        "sunday_font_color": "FFFF0000",
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

    @property
    def priority(self) -> dict[str, Any]:
        return self.raw["priority"]

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
