"""待機可否の判定と、曜日ごとの優先順位（tier）の算出。

「カテ待機表 作成手順」の 3.〜4. をコードにしたもの。
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass

from .config import Config, normalize_code
from .workbook import WorkSchedule

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


@dataclass(frozen=True)
class Eligibility:
    """ある人のある日の待機可否。"""

    ok: bool
    reason: str = ""


class RuleEngine:
    """勤務表＋設定から、日ごと・人ごとの待機可否と優先順位を判定する。"""

    def __init__(self, cfg: Config, schedule: WorkSchedule, year: int, month: int):
        self.cfg = cfg
        self.schedule = schedule
        self.year = year
        self.month = month
        self.days_in_month = calendar.monthrange(year, month)[1]
        self.days = [dt.date(year, month, d) for d in range(1, self.days_in_month + 1)]
        self.members = cfg.member_names
        self.holidays = cfg.holidays
        self.absent_always = cfg.absent_always
        self.absent_if_red = cfg.absent_if_red
        self.duty_source = cfg.priority.get("duty_source", "both")
        self.weekend_pool = set(cfg.weekend_pool) or set(self.members)
        self._elig_cache: dict[tuple[str, dt.date], Eligibility] = {}

    # -- 日付まわり --------------------------------------------------------
    def weekday(self, day: dt.date) -> int:
        return day.weekday()

    def is_holiday(self, day: dt.date) -> bool:
        return day in self.holidays

    def is_red_day(self, day: dt.date) -> bool:
        """カレンダー上で赤字にする日（日曜・祝日）。"""
        return day.weekday() == SUN or self.is_holiday(day)

    # -- セルの読み取り ----------------------------------------------------
    def codes(self, name: str, day: dt.date) -> list[str]:
        """その日の勤務記号（既定では上下段の両方）。"""
        return self.schedule.day_cells(name, day).texts(self.duty_source)

    def is_yellow(self, name: str, day: dt.date) -> bool:
        return self.schedule.day_cells(name, day).yellow

    def has_red_text(self, name: str, day: dt.date) -> bool:
        """赤字の「本人希望の不在」があるか。

        実際の勤務表では、赤字は不在表記（公・有・夏 など）だけでなく
        カテ・ABL の強調にも使われている。既定では不在表記の赤字だけを
        本人希望の不在として扱う（plan_codes.red_scope: any で全赤字扱い）。
        """
        scope = self.cfg.raw["plan_codes"].get("red_scope", "absence_codes")
        absent_codes = self.absent_always | self.absent_if_red
        for cell in self.schedule.day_cells(name, day).cells:
            if not (cell.red and cell.text):
                continue
            if scope == "any" or cell.text in absent_codes:
                return True
        return False

    def duty_codes(self, name: str, day: dt.date) -> list[str]:
        """勤務内容の記号（不在記号を除いたもの）。"""
        absent = self.absent_always | self.absent_if_red
        return [c for c in self.codes(name, day) if c not in absent]

    def is_absent(self, name: str, day: dt.date) -> bool:
        """作成手順 3.① の「不在者」判定。

        * 有 / 夏 / リ / 出 / 有/公 … 色に関わらず不在
        * 公 … 赤字のときだけ不在（黒字なら祝日等の一斉「公」なので待機可能）
        * ―/公（日勤/公休）や勤務記号がある日は不在ではない
        """
        codes = self.codes(name, day)
        if not codes:
            return False
        if self.duty_codes(name, day):
            return False
        if any(c in self.absent_always for c in codes):
            return True
        if any(c in self.absent_if_red for c in codes) and self.has_red_text(name, day):
            return True
        return False

    def is_working(self, name: str, day: dt.date) -> bool:
        return not self.is_absent(name, day)

    # -- 待機可否 ----------------------------------------------------------
    def eligibility(self, name: str, day: dt.date) -> Eligibility:
        key = (name, day)
        if key not in self._elig_cache:
            self._elig_cache[key] = self._eligibility(name, day)
        return self._elig_cache[key]

    def eligible(self, name: str, day: dt.date) -> bool:
        return self.eligibility(name, day).ok

    def _eligibility(self, name: str, day: dt.date) -> Eligibility:
        wd = day.weekday()

        # 4. 土日は担当プールが限定される
        if wd in (SAT, SUN) and name not in self.weekend_pool:
            return Eligibility(False, "土日の担当対象外")

        # 3.② 黄色セル（本人希望）
        if self.is_yellow(name, day):
            return Eligibility(False, "黄色セル（本人希望）")

        # 3.①/3.⑥ 不在者・赤字（本人希望の不在）
        if self.is_absent(name, day):
            codes = "/".join(self.codes(name, day)) or "記載なし"
            red = "・赤字" if self.has_red_text(name, day) else ""
            return Eligibility(False, f"不在（{codes}{red}）")

        # 3.③ バックアップ役が不在の日は従属者も不可
        anchor = self.cfg.backup_anchor
        if anchor and name in self.cfg.backup_dependents and self.is_absent(anchor, day):
            return Eligibility(False, f"{anchor}が不在（バックアップ不可）")

        # 4. 日曜の除外条件：前日(土)不在・翌日(月)不在
        if wd == SUN:
            prev_day = day - dt.timedelta(days=1)
            next_day = day + dt.timedelta(days=1)
            if self.is_absent(name, prev_day):
                return Eligibility(False, "前日(土)が不在")
            if self.is_absent(name, next_day):
                return Eligibility(False, "翌日(月)が不在")

        return Eligibility(True)

    def candidates(self, day: dt.date) -> list[str]:
        return [n for n in self.members if self.eligible(n, day)]

    # -- 優先順位 ----------------------------------------------------------
    def next_day_duties(self, name: str, day: dt.date) -> list[str]:
        return self.duty_codes(name, day + dt.timedelta(days=1))

    def tier(self, name: str, day: dt.date) -> int | None:
        """作成手順 4. の優先順位。0 が第1優先。該当なしは None。"""
        wd = day.weekday()
        if wd == SAT:
            return 0
        if wd == FRI:
            nxt = day + dt.timedelta(days=1)
            return 0 if self.is_working(name, nxt) else 1
        tiers = self.cfg.priority["sun" if wd == SUN else "mon_thu"]
        duties = self.next_day_duties(name, day)
        for index, group in enumerate(tiers):
            wanted = {normalize_code(c) for c in group}
            if "" in wanted and not duties:
                return index
            if duties and any(d in wanted for d in duties):
                return index
        return None

    def tier_label(self, name: str, day: dt.date) -> str:
        t = self.tier(name, day)
        if t is None:
            return "該当なし"
        wd = day.weekday()
        if wd == SAT:
            return "土曜（優先順位なし）"
        if wd == FRI:
            return "第1優先(翌日勤務あり)" if t == 0 else "第2優先(その他)"
        return f"第{t + 1}優先"

    # -- 集計 --------------------------------------------------------------
    def next_duty_text(self, name: str, day: dt.date) -> str:
        duties = self.next_day_duties(name, day)
        if duties:
            return "/".join(duties)
        codes = self.codes(name, day + dt.timedelta(days=1))
        return "/".join(codes) if codes else "（空白）"
