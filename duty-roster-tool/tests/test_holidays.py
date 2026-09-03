import datetime as dt

from duty_roster.holidays_jp import holidays_in_month, japanese_holidays


def test_fixed_and_happy_monday_holidays_2026():
    days = japanese_holidays(2026)
    assert days[dt.date(2026, 1, 1)] == "元日"
    assert days[dt.date(2026, 1, 12)] == "成人の日"      # 1月第2月曜
    assert days[dt.date(2026, 8, 11)] == "山の日"
    assert days[dt.date(2026, 10, 12)] == "スポーツの日"  # 10月第2月曜


def test_equinox_2026():
    days = japanese_holidays(2026)
    assert days[dt.date(2026, 3, 20)] == "春分の日"
    assert days[dt.date(2026, 9, 23)] == "秋分の日"


def test_substitute_and_citizens_holiday_2026():
    days = japanese_holidays(2026)
    assert days[dt.date(2026, 5, 6)] == "振替休日"        # 5/3 が日曜
    assert days[dt.date(2026, 9, 22)] == "国民の休日"      # 敬老の日と秋分の日に挟まれる


def test_holidays_in_month():
    assert set(holidays_in_month(2026, 8)) == {dt.date(2026, 8, 11)}
