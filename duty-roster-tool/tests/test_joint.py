"""待機と予備を同時に組むモード。"""

import datetime as dt

import pytest

from duty_roster.backup import solve_backup
from duty_roster.config import load_config
from duty_roster.joint import solve_joint
from duty_roster.rules import RuleEngine
from duty_roster.sample import build_sample
from duty_roster.solver import solve
from duty_roster.workbook import read_schedule

CFG = load_config("config/roster.example.yaml")
YEAR, MONTH = 2026, 8


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    work = tmp_path_factory.mktemp("joint")
    schedule = read_schedule(build_sample(work / "s.xlsx", YEAR, MONTH), YEAR, MONTH, CFG)
    return RuleEngine(CFG, schedule, YEAR, MONTH)


@pytest.fixture(scope="module")
def both(engine):
    return solve_joint(CFG, engine)


def test_quota_is_kept(both, engine):
    """同時に組んでも待機の回数配分は崩れない。"""
    primary, _ = both
    quota = CFG.quota(engine.days_in_month)
    for name, target in quota.items():
        assert primary.counts.get(name, 0) == target


def test_every_day_has_a_different_pair(both, engine):
    primary, backup = both
    for day in engine.days:
        assert primary.assignment[day] != backup.assignment[day]


def test_forced_anchor_days_are_respected(both, engine):
    """待機が依存2名の日は、予備がバックアップ役になる。"""
    primary, backup = both
    anchor = CFG.backup_anchor
    for day in engine.days:
        if primary.assignment[day] in CFG.backup_dependents:
            assert backup.assignment[day] == anchor


def test_no_worse_than_solving_in_two_stages(both, engine):
    """同時に組んだほうが、待機＋予備の連日は増えない。"""
    primary, backup = both
    staged_primary = solve(CFG, engine)
    staged_backup = solve_backup(CFG, engine, staged_primary.assignment)

    def runs(p, b):
        days_of: dict[str, set[dt.date]] = {}
        for mapping in (p, b):
            for day, name in mapping.items():
                days_of.setdefault(name, set()).add(day)
        return sum(
            1
            for days in days_of.values()
            for day in days
            if day + dt.timedelta(days=1) in days
        )

    assert runs(primary.assignment, backup.assignment) <= runs(
        staged_primary.assignment, staged_backup.assignment
    )
