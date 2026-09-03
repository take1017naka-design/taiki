"""日本の祝日（国民の祝日に関する法律）の計算。

祝日は「日付を赤字にする」だけでなく、「祝日の『公』は赤字でなければ待機可能」
というルールに直結する。設定への書き忘れで結果が変わってしまうため自動計算する。
手動で足したい日は設定の `holidays` に書ける（両方が使われる）。
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache

FIXED = {
    (1, 1): "元日",
    (2, 11): "建国記念の日",
    (2, 23): "天皇誕生日",
    (4, 29): "昭和の日",
    (5, 3): "憲法記念日",
    (5, 4): "みどりの日",
    (5, 5): "こどもの日",
    (8, 11): "山の日",
    (11, 3): "文化の日",
    (11, 23): "勤労感謝の日",
}
# (月, 第n, 曜日=月曜0) → 名称
HAPPY_MONDAY = {
    (1, 2): "成人の日",
    (7, 3): "海の日",
    (9, 3): "敬老の日",
    (10, 2): "スポーツの日",
}


def _nth_monday(year: int, month: int, nth: int) -> dt.date:
    first = dt.date(year, month, 1)
    offset = (0 - first.weekday()) % 7
    return first + dt.timedelta(days=offset + 7 * (nth - 1))


def _equinox(year: int, spring: bool) -> dt.date:
    """春分・秋分の日（1980〜2099年に有効な近似式）。"""
    base = 20.8431 if spring else 23.2488
    day = int(base + 0.242194 * (year - 1980) - (year - 1980) // 4)
    return dt.date(year, 3 if spring else 9, day)


@lru_cache(maxsize=32)
def japanese_holidays(year: int) -> dict[dt.date, str]:
    """その年の祝日（振替休日・国民の休日を含む）。"""
    days: dict[dt.date, str] = {}
    for (month, day), name in FIXED.items():
        days[dt.date(year, month, day)] = name
    for (month, nth), name in HAPPY_MONDAY.items():
        days[_nth_monday(year, month, nth)] = name
    days[_equinox(year, spring=True)] = "春分の日"
    days[_equinox(year, spring=False)] = "秋分の日"

    # 振替休日: 祝日が日曜なら、その後の最初の平日
    for day in sorted(d for d in days if d.weekday() == 6):
        nxt = day + dt.timedelta(days=1)
        while nxt in days:
            nxt += dt.timedelta(days=1)
        days[nxt] = "振替休日"

    # 国民の休日: 祝日に挟まれた平日
    for day in sorted(days):
        candidate = day + dt.timedelta(days=1)
        after = candidate + dt.timedelta(days=1)
        if candidate not in days and after in days and candidate.weekday() != 6:
            days[candidate] = "国民の休日"

    return days


def holidays_in_month(year: int, month: int) -> dict[dt.date, str]:
    return {d: name for d, name in japanese_holidays(year).items() if d.month == month}
