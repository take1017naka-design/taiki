import datetime as dt

from duty_roster.config import load_config
from duty_roster.rules import RuleEngine
from duty_roster.sample import build_sample
from duty_roster.solver import solve
from duty_roster.workbook import read_schedule
from duty_roster.writer import write_roster

CFG = load_config("config/roster.example.yaml")


import pytest


def _run(tmp_path, year, month):
    path = build_sample(tmp_path / f"sample_{year}{month:02d}.xlsx", year, month)
    schedule = read_schedule(path, year, month, CFG)
    engine = RuleEngine(CFG, schedule, year, month)
    return engine, solve(CFG, engine)


@pytest.fixture(scope="module")
def august(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("aug"), 2026, 8)


@pytest.fixture(scope="module")
def february(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("feb"), 2026, 2)


def test_every_day_is_assigned_and_quota_is_exact(august):
    engine, solution = august
    assert set(solution.assignment) == set(engine.days)
    assert solution.counts == CFG.quota(engine.days_in_month)


def test_no_assignment_on_unavailable_day(august):
    engine, solution = august
    bad = [
        (day, name)
        for day, name in solution.assignment.items()
        if not engine.eligible(name, day)
    ]
    assert bad == []


def test_sunday_uses_each_member_at_most_once(august):
    engine, solution = august
    sundays = [d for d in engine.days if d.weekday() == 6]
    names = [solution.assignment[d] for d in sundays]
    assert len(set(names)) == len(names)
    assert set(names) <= set(CFG.weekend_pool)


def test_consecutive_group_never_runs_three_days(august):
    engine, solution = august
    group = set(CFG.consecutive_group)
    days = engine.days
    runs = [
        days[i]
        for i in range(len(days) - 2)
        if all(solution.assignment[days[i + k]] in group for k in range(3))
    ]
    assert runs == []


def test_writer_produces_all_sheets(august, tmp_path):
    engine, solution = august
    out = write_roster(tmp_path / "roster.xlsx", CFG, engine, solution)
    from openpyxl import load_workbook

    wb = load_workbook(out)
    assert wb.sheetnames == ["待機表", "一覧", "集計", "可否一覧", "確認事項"]
    assert wb["待機表"]["A1"].value == "2026年8月　カテ待機表"


def test_short_month_also_solves(february):
    engine, solution = february
    assert solution.counts == CFG.quota(28)
