import datetime as dt

import pytest

from duty_roster.backup import solve_backup
from duty_roster.config import load_config
from duty_roster.rules import RuleEngine
from duty_roster.sample import build_sample
from duty_roster.solver import solve
from duty_roster.workbook import read_schedule
from duty_roster.writer import write_roster

CFG = load_config("config/roster.example.yaml")
YEAR, MONTH = 2026, 8


@pytest.fixture(scope="module")
def rosters(tmp_path_factory):
    path = build_sample(tmp_path_factory.mktemp("bk") / "sample.xlsx", YEAR, MONTH)
    engine = RuleEngine(CFG, read_schedule(path, YEAR, MONTH, CFG), YEAR, MONTH)
    primary = solve(CFG, engine)
    backup = solve_backup(CFG, engine, primary.assignment)
    return engine, primary, backup


def test_every_day_has_a_backup(rosters):
    engine, _, backup = rosters
    assert set(backup.assignment) == set(engine.days)


def test_backup_is_a_different_person(rosters):
    engine, primary, backup = rosters
    same = [d for d in engine.days if backup.assignment[d] == primary.assignment[d]]
    assert same == []


def test_anchor_covers_the_dependents(rosters):
    """待機が依存2名の日は、必ずバックアップ役が予備に入る。"""
    engine, primary, backup = rosters
    anchor = CFG.backup_anchor
    dependents = set(CFG.backup_dependents)
    days = [d for d in engine.days if primary.assignment[d] in dependents]
    assert days, "サンプルに依存2名の待機日がない"
    for day in days:
        assert backup.assignment[day] == anchor
        assert day in backup.forced


def test_forbidden_pairs_are_respected(rosters):
    engine, primary, backup = rosters
    for day in engine.days:
        blocked = CFG.backup_forbidden_pairs.get(primary.assignment[day], set())
        assert backup.assignment[day] not in blocked


def test_combined_runs_stay_within_the_limit(rosters):
    """待機と予備を合算した連続日数が上限を超えない。"""
    engine, primary, backup = rosters
    for name in engine.members:
        days = sorted(
            {d for d in engine.days if primary.assignment[d] == name}
            | {d for d in engine.days if backup.assignment[d] == name}
        )
        limit = CFG.backup_max_run(name)
        run = 1
        for earlier, later in zip(days, days[1:]):
            run = run + 1 if (later - earlier).days == 1 else 1
            assert run <= limit, f"{name} が {later:%m/%d} まで {run} 日連続（上限{limit}）"


def test_backup_avoids_unavailable_people(rosters):
    engine, _, backup = rosters
    for day in engine.days:
        name = backup.assignment[day]
        if engine.backup_eligible(name, day):
            continue
        # 候補が誰もいない日だけは埋めたうえで違反として報告する
        assert not [n for n in engine.members if engine.backup_eligible(n, day)]
        assert any(f"{day:%m/%d}" in v for v in backup.violations)


def test_backup_workbook_has_the_same_format(rosters, tmp_path):
    engine, primary, backup = rosters
    out = write_roster(
        tmp_path / "backup.xlsx",
        CFG,
        engine,
        backup,
        sheet_name="予備待機表",
        title="カテ予備待機表",
        partner=primary.assignment,
        availability_fn=engine.backup_eligibility,
    )
    from openpyxl import load_workbook

    wb = load_workbook(out)
    assert wb.sheetnames == ["予備待機表", "一覧", "集計", "可否一覧", "確認事項"]
    ws = wb["予備待機表"]
    assert ws["A1"].value == f"{YEAR}年{MONTH}月　カテ予備待機表"
    assert ws.page_setup.orientation == "landscape"
    assert wb["一覧"]["D1"].value == "待機者"   # 待機者の列が入る
