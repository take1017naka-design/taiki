"""待機可否の判定と、曜日ごとの優先順位（tier）の算出。

「カテ待機表 作成手順」の 3.〜4. をコードにしたもの。
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass

from .config import Config, normalize_code
from .holidays_jp import japanese_holidays
from .workbook import WorkSchedule

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


@dataclass(frozen=True)
class Eligibility:
    """ある人のある日の待機可否。

    penalty > 0 は「条件付きで可」。他に組めないときだけ使う候補で、
    探索では追加コストとして扱われるため、通常は選ばれない。
    """

    ok: bool
    reason: str = ""
    penalty: float = 0.0
    note: str = ""

    @property
    def conditional(self) -> bool:
        return self.ok and self.penalty > 0


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
        self.holidays = set(cfg.holidays)
        if cfg.holidays_auto:
            self.holidays |= {d for d in japanese_holidays(year) if d.month == month}
        self.absent_always = cfg.absent_always
        self.absent_if_red = cfg.absent_if_red
        self.holiday_relaxed = cfg.holiday_relaxed
        self.duty_source = cfg.priority.get("duty_source", "both")
        self.weekend_pool = set(cfg.weekend_pool) or set(self.members)
        self.sun_blocked_next_duties = cfg.sun_blocked_next_duties
        self.manual_unavailable = cfg.manual_unavailable
        self._elig_cache: dict[tuple[str, dt.date], Eligibility] = {}
        self._all_absent_cache: dict[dt.date, bool] = {}

    # -- 日付まわり --------------------------------------------------------
    def weekday(self, day: dt.date) -> int:
        return day.weekday()

    def is_holiday(self, day: dt.date) -> bool:
        return day in self.holidays

    def is_red_day(self, day: dt.date) -> bool:
        """カレンダー上で赤字にする日（日曜・祝日）。"""
        return day.weekday() == SUN or self.is_holiday(day)

    def is_holiday_like(self, day: dt.date) -> bool:
        """祝日または日曜。全員が「公」になるため不在の判定を緩める。"""
        return self.is_red_day(day)

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

        * 公 / 有 / 夏 / リ / 出 / 有/公 … 色に関わらず不在（黒字でも不在）
        * ただし祝日・日曜の「公」だけは赤字でなければ不在としない
        * ―/公（日勤/公休）や勤務記号がある日は不在ではない
        """
        codes = self.codes(name, day)
        if not codes:
            return False
        if self.duty_codes(name, day):
            return False
        always, if_red = self.absent_always, self.absent_if_red
        if self.is_holiday_like(day):
            # 祝日・日曜の「公」は赤字でなければ待機可能
            always = always - self.holiday_relaxed
            if_red = if_red | self.holiday_relaxed
        if any(c in always for c in codes):
            return True
        if any(c in if_red for c in codes) and self.has_red_text(name, day):
            return True
        return False

    def is_working(self, name: str, day: dt.date) -> bool:
        return not self.is_absent(name, day)

    # -- 全員不在の日 ------------------------------------------------------
    def relevant_members(self, day: dt.date) -> list[str]:
        """その日に待機を担当しうる人（土日は担当プールに限る）。"""
        if day.weekday() in (SAT, SUN):
            return [n for n in self.members if n in self.weekend_pool]
        return list(self.members)

    def is_all_absent_day(self, day: dt.date) -> bool:
        """対象者全員が不在の日か（日曜・祝日の一斉「公」など）。

        この日は不在を理由とする待機不可を解除する。誰も選べなくなるため。
        """
        if not self.cfg.raw["roles"].get("all_absent_exception", True):
            return False
        if day not in self._all_absent_cache:
            pool = self.relevant_members(day)
            self._all_absent_cache[day] = bool(pool) and all(
                self.is_absent(n, day) for n in pool
            )
        return self._all_absent_cache[day]

    def is_long_weekend_start(self, day: dt.date) -> bool:
        """その日の翌日が休み（祝日、または対象者全員が不在）か。

        連休の場合、日曜の「翌日(月)に出勤する人」という条件を外す。
        """
        nxt = day + dt.timedelta(days=1)
        return self.is_holiday_like(nxt) or self.is_all_absent_day(nxt)

    @property
    def exception_days(self) -> list[dt.date]:
        return [d for d in self.days if self.is_all_absent_day(d)]

    # -- 待機可否 ----------------------------------------------------------
    def eligibility(self, name: str, day: dt.date) -> Eligibility:
        key = (name, day)
        if key not in self._elig_cache:
            self._elig_cache[key] = self._eligibility(name, day)
        return self._elig_cache[key]

    def eligible(self, name: str, day: dt.date) -> bool:
        return self.eligibility(name, day).ok

    def availability_mark(self, name: str, day: dt.date) -> str:
        elig = self.eligibility(name, day)
        if not elig.ok:
            return "×"
        return "△" if elig.conditional else "○"

    def _eligibility(self, name: str, day: dt.date) -> Eligibility:
        wd = day.weekday()

        # 0. 設定での手動指定（勤務表から読み取れない事情）
        manual = self.manual_unavailable.get(name, {})
        if day in manual:
            return Eligibility(False, f"手動で待機不可に指定（{manual[day]}）")

        # 4. 土日は担当プールが限定される
        if wd in (SAT, SUN) and name not in self.weekend_pool:
            return Eligibility(False, "土日の担当対象外")

        # 3.② 黄色セル（本人希望）
        if self.is_yellow(name, day):
            return Eligibility(False, "黄色セル（本人希望）")

        # 3.⑥ 赤字の不在表記は本人希望の不在（祝日の「公」でも解除しない）
        if self.has_red_text(name, day):
            return Eligibility(False, "赤字（本人希望の不在）")

        # 3.① 不在者
        # 全員が不在の日（日曜・祝日の一斉「公」）だけは、不在を理由にしない。
        if self.is_absent(name, day) and not self.is_all_absent_day(day):
            return Eligibility(False, f"不在（{'/'.join(self.codes(name, day)) or '記載なし'}）")

        # 3.③ バックアップ役が不在の日は従属者も不可
        anchor = self.cfg.backup_anchor
        if anchor and name in self.cfg.backup_dependents and self.is_absent(anchor, day):
            return Eligibility(False, f"{anchor}が不在（バックアップ不可）")

        # 4. 日曜の除外条件
        if wd == SUN:
            prev_day = day - dt.timedelta(days=1)
            next_day = day + dt.timedelta(days=1)
            # 連休（翌日が祝日、または全員不在）なら翌日の条件は問わない
            if not self.is_long_weekend_start(day):
                # 翌日(月)が不在の人は対象外（日曜は翌日出勤者が担当する）
                if self.is_absent(name, next_day):
                    return Eligibility(False, "翌日(月)が不在")
                # 翌日(月)が手術室勤務（空白・OP・アーム）だけの人は対象外
                duties = self.next_day_duties(name, day)
                if not [d for d in duties if d not in self.sun_blocked_next_duties]:
                    label = "/".join(duties) if duties else "空白"
                    return Eligibility(False, f"翌日(月)が手術室勤務（{label}）")
            # 前日(土)が不在の人は、他に組めない場合に限って候補にする。
            # 当日(日)が赤字・黄色でないことは、ここまでの判定で確認済み。
            if self.is_absent(name, prev_day):
                return Eligibility(
                    True,
                    penalty=float(self.cfg.weights.get("sunday_prev_absent", 2000)),
                    note="前日(土)が不在（他に組めない場合の候補）",
                )

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
