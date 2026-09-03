import datetime as dt

from duty_roster.config import load_config
from duty_roster.rules import RuleEngine
from duty_roster.workbook import Cell, DayCells, WorkSchedule

CFG = load_config("config/roster.example.yaml")
YEAR, MONTH = 2026, 8


def build_engine(cells: dict[tuple[str, dt.date], list[Cell]]) -> RuleEngine:
    schedule = WorkSchedule(
        year=YEAR,
        month=MONTH,
        cells={key: DayCells(list(value)) for key, value in cells.items()},
        names_in_sheet=CFG.member_names,
    )
    return RuleEngine(CFG, schedule, YEAR, MONTH)


def d(day: int) -> dt.date:
    return dt.date(YEAR, MONTH, day)


def test_black_kou_is_available_but_red_kou_is_not():
    engine = build_engine(
        {
            ("担当C", d(11)): [Cell(text="公")],
            ("担当D", d(11)): [Cell(text="公", red=True)],
        }
    )
    assert engine.eligible("担当C", d(11))
    assert not engine.eligible("担当D", d(11))
    assert not engine.is_absent("担当C", d(11))
    assert engine.is_absent("担当D", d(11))


def test_absence_codes_block_regardless_of_color():
    engine = build_engine({("担当C", d(4)): [Cell(text=code)] for code in ["有"]})
    assert not engine.eligible("担当C", d(4))

    engine = build_engine({("担当C", d(4)): [Cell(text="有/公")]})
    assert not engine.eligible("担当C", d(4))


def test_dash_kou_is_working():
    engine = build_engine({("担当C", d(4)): [Cell(text="―/公")]})
    assert engine.eligible("担当C", d(4))
    assert not engine.is_absent("担当C", d(4))


def test_red_on_duty_code_does_not_block():
    """赤字は カテ・ABL の強調にも使われるため、不在表記の赤字だけを見る。"""
    engine = build_engine({("担当C", d(4)): [Cell(text="ABL", red=True)]})
    assert engine.eligible("担当C", d(4))


def test_yellow_cell_blocks():
    engine = build_engine({("担当C", d(4)): [Cell(text="ME", yellow=True)]})
    assert not engine.eligible("担当C", d(4))
    assert "黄色" in engine.eligibility("担当C", d(4)).reason


def test_anchor_absence_blocks_dependents():
    engine = build_engine({("担当A", d(4)): [Cell(text="有")]})
    assert not engine.eligible("担当G", d(4))
    assert not engine.eligible("担当H", d(4))
    assert engine.eligible("担当C", d(4))


def test_weekend_pool_only_on_saturday_and_sunday():
    engine = build_engine({})
    assert not engine.eligible("担当A", d(1))   # 土
    assert not engine.eligible("担当G", d(2))   # 日
    assert engine.eligible("担当B", d(1))


def test_sunday_excludes_previous_saturday_and_next_monday_absence():
    engine = build_engine({("担当B", d(1)): [Cell(text="有")]})
    assert not engine.eligible("担当B", d(2))
    engine = build_engine({("担当B", d(3)): [Cell(text="夏")]})
    assert not engine.eligible("担当B", d(2))


def test_priority_tiers_follow_next_day_duty():
    engine = build_engine(
        {
            ("担当C", d(4)): [Cell(text="ME")],
            ("担当C", d(5)): [Cell(text="ME")],
            ("担当D", d(5)): [Cell(text="内視")],
            ("担当E", d(5)): [Cell(text="機")],
            ("担当F", d(5)): [Cell(text="OP")],
        }
    )
    assert engine.tier("担当C", d(4)) == 0     # 翌日 ME
    assert engine.tier("担当D", d(4)) == 1     # 翌日 内視
    assert engine.tier("担当E", d(4)) == 2     # 翌日 機
    assert engine.tier("担当F", d(4)) == 3     # 翌日 OP
    assert engine.tier("担当A", d(4)) == 3     # 翌日 空白


def test_friday_prefers_people_working_on_saturday():
    engine = build_engine(
        {
            ("担当C", d(8)): [Cell(text="ME")],
            ("担当D", d(8)): [Cell(text="有")],
        }
    )
    assert engine.tier("担当C", d(7)) == 0
    assert engine.tier("担当D", d(7)) == 1
