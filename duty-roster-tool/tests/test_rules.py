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


def test_kou_is_absent_even_in_black_on_a_normal_weekday():
    """黒字でも不在は待機不可（祝日・日曜を除く）。"""
    engine = build_engine(
        {
            ("担当C", d(4)): [Cell(text="公")],
            ("担当D", d(4)): [Cell(text="公", red=True)],
        }
    )
    assert not engine.is_holiday_like(d(4))
    assert engine.is_absent("担当C", d(4))
    assert not engine.eligible("担当C", d(4))
    assert not engine.eligible("担当D", d(4))


def test_holiday_kou_is_available_unless_red():
    """祝日（8/11 山の日）の「公」は赤字でなければ待機可能。"""
    engine = build_engine(
        {
            ("担当C", d(11)): [Cell(text="公")],
            ("担当D", d(11)): [Cell(text="公", red=True)],
        }
    )
    assert engine.is_holiday_like(d(11))
    assert engine.eligible("担当C", d(11))
    assert not engine.eligible("担当D", d(11))


def test_sunday_kou_is_available_unless_red():
    engine = build_engine(
        {
            ("担当C", d(2)): [Cell(text="公")],
            ("担当C", d(3)): [Cell(text="ME")],
            ("担当D", d(2)): [Cell(text="公", red=True)],
            ("担当D", d(3)): [Cell(text="ME")],
        }
    )
    assert engine.eligible("担当C", d(2))
    assert not engine.eligible("担当D", d(2))


def test_sunday_operating_room_monday_is_only_conditional():
    """翌日(月)が手術室勤務（空白・OP・アーム）だけの人は、他に組めない場合の候補(△)。"""
    engine = build_engine(
        {
            ("担当C", d(2)): [Cell(text="公")],
            ("担当C", d(3)): [],                      # 空白＝手術室
            ("担当D", d(2)): [Cell(text="公")],
            ("担当D", d(3)): [Cell(text="OP")],
            ("担当E", d(2)): [Cell(text="公")],
            ("担当E", d(3)): [Cell(text="内視")],
        }
    )
    assert engine.availability_mark("担当C", d(2)) == "△"
    assert "手術室" in engine.eligibility("担当C", d(2)).note
    assert engine.availability_mark("担当D", d(2)) == "△"
    assert engine.availability_mark("担当E", d(2)) == "○"
    # 手術室(△)は前日(土)不在(△)より重い＝より後回し
    assert (
        engine.eligibility("担当C", d(2)).penalty
        > float(CFG.weights["sunday_prev_absent"])
    )


def test_long_weekend_lifts_the_monday_condition():
    """連休（翌日が祝日）なら、翌日の勤務内容や不在を問わない。"""
    # 2026-09-20(日) の翌日 9/21 は敬老の日
    import datetime

    from duty_roster.rules import RuleEngine
    from duty_roster.workbook import DayCells, WorkSchedule

    cells = {
        ("担当C", datetime.date(2026, 9, 20)): DayCells([Cell(text="公")]),
        ("担当C", datetime.date(2026, 9, 21)): DayCells([Cell(text="公")]),
        ("担当D", datetime.date(2026, 9, 20)): DayCells([Cell(text="公", red=True)]),
    }
    schedule = WorkSchedule(2026, 9, cells, CFG.member_names)
    engine = RuleEngine(CFG, schedule, 2026, 9)
    sunday = datetime.date(2026, 9, 20)
    assert engine.is_long_weekend_start(sunday)
    assert engine.eligible("担当C", sunday)      # 翌日が空白でも可
    assert not engine.eligible("担当D", sunday)  # 当日が赤字なら不可


def test_holiday_prefers_the_person_actually_working():
    """祝日は、その日に出勤している人を待機にする。"""
    import datetime

    from duty_roster.rules import RuleEngine
    from duty_roster.workbook import DayCells, WorkSchedule

    holiday = datetime.date(2026, 8, 11)  # 山の日
    cells = {(name, holiday): DayCells([Cell(text="公")]) for name in CFG.member_names}
    cells[("担当E", holiday)] = DayCells([Cell(text="―/公"), Cell(text="ME")])
    schedule = WorkSchedule(2026, 8, cells, CFG.member_names)
    engine = RuleEngine(CFG, schedule, 2026, 8)

    assert engine.is_holiday(holiday)
    assert engine.holiday_workers(holiday) == ["担当E"]
    assert engine.tier_label("担当E", holiday) == "祝日（当日出勤）"
    assert engine.tier_label("担当C", holiday) == "祝日（当日出勤者以外）"


def test_holiday_without_any_worker_uses_normal_priority():
    import datetime

    from duty_roster.rules import RuleEngine
    from duty_roster.workbook import DayCells, WorkSchedule

    holiday = datetime.date(2026, 8, 11)
    cells = {(name, holiday): DayCells([Cell(text="公")]) for name in CFG.member_names}
    schedule = WorkSchedule(2026, 8, cells, CFG.member_names)
    engine = RuleEngine(CFG, schedule, 2026, 8)
    assert engine.holiday_workers(holiday) == []
    assert engine.tier_label("担当C", holiday).startswith("第")


def test_manual_unavailable_blocks_the_day():
    import copy

    from duty_roster.config import Config

    raw = copy.deepcopy(CFG.raw)
    raw["manual_unavailable"] = {"担当C": ["2026-08-04"]}
    cfg = Config(raw=raw)
    schedule = WorkSchedule(YEAR, MONTH, {}, cfg.member_names)
    engine = RuleEngine(cfg, schedule, YEAR, MONTH)
    assert not engine.eligible("担当C", d(4))
    assert "手動" in engine.eligibility("担当C", d(4)).reason
    assert engine.eligible("担当D", d(4))


def test_sunday_needs_someone_working_on_monday():
    engine = build_engine(
        {
            ("担当C", d(2)): [Cell(text="公")],
            ("担当C", d(3)): [Cell(text="公")],       # 翌日(月)が不在
            ("担当D", d(2)): [Cell(text="公")],
            ("担当D", d(3)): [Cell(text="ME")],       # 翌日(月)は出勤
        }
    )
    assert not engine.eligible("担当C", d(2))
    assert engine.eligible("担当D", d(2))


def test_all_absent_day_lifts_the_absence_rule():
    """全員が一斉に「公」の日（日曜・祝日）は、不在を理由にしない。"""
    cells = {(name, d(4)): [Cell(text="夏")] for name in CFG.member_names}
    cells[("担当D", d(4))] = [Cell(text="公", red=True)]
    engine = build_engine(cells)

    assert engine.is_all_absent_day(d(4))
    assert engine.eligible("担当C", d(4))
    assert not engine.eligible("担当D", d(4))           # 赤字は解除されない
    assert not engine.eligible("担当G", d(4))           # バックアップ役が不在


def test_all_absent_exception_only_applies_when_everyone_is_absent():
    cells = {(name, d(4)): [Cell(text="夏")] for name in CFG.member_names}
    cells[("担当C", d(4))] = [Cell(text="ME")]
    engine = build_engine(cells)

    assert not engine.is_all_absent_day(d(4))
    assert engine.eligible("担当C", d(4))
    assert not engine.eligible("担当E", d(4))


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


def test_sunday_excludes_next_monday_absence():
    engine = build_engine({("担当B", d(3)): [Cell(text="夏")]})
    assert not engine.eligible("担当B", d(2))
    assert engine.eligibility("担当B", d(2)).reason == "翌日(月)が不在"


def test_sunday_previous_saturday_absence_is_only_conditional():
    """前日(土)不在は、他に組めないときだけ使う候補（当日が赤字でなければ可）。"""
    engine = build_engine(
        {("担当B", d(1)): [Cell(text="有")], ("担当B", d(3)): [Cell(text="ME")]}
    )
    elig = engine.eligibility("担当B", d(2))
    assert elig.ok
    assert elig.conditional
    assert engine.availability_mark("担当B", d(2)) == "△"


def test_sunday_red_stays_impossible_even_with_saturday_absence():
    engine = build_engine(
        {
            ("担当B", d(1)): [Cell(text="有")],
            ("担当B", d(2)): [Cell(text="公", red=True)],
            ("担当B", d(3)): [Cell(text="ME")],
        }
    )
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
    assert engine.tier("担当E", d(4)) == 3     # 翌日 機
    assert engine.tier("担当F", d(4)) == 4     # 翌日 OP
    assert engine.tier("担当A", d(4)) == 4     # 翌日 空白


def test_other_duty_codes_rank_between_naishi_and_ki():
    """災・業・労・研修・材料 は「内視」と「機」の間の優先順位。

    この5つも勤務として判定するので、翌日がこれらの日は手術室ではない。
    """
    engine = build_engine(
        {
            ("担当C", d(5)): [Cell(text="内視")],
            ("担当D", d(5)): [Cell(text="研修")],
            ("担当E", d(5)): [Cell(text="材料")],
            ("担当F", d(5)): [Cell(text="機")],
        }
    )
    assert not engine.next_day_is_operating_room("担当D", d(4))
    assert engine.tier("担当C", d(4)) == 1
    assert engine.tier("担当D", d(4)) == 2
    assert engine.tier("担当E", d(4)) == 2
    assert engine.tier("担当F", d(4)) == 3


def test_other_duty_codes_count_as_working():
    """これらの記号の日は出勤扱いなので、その前日は待機可能。"""
    engine = build_engine({("担当C", d(5)): [Cell(text="災")]})
    assert engine.is_working("担当C", d(5))
    assert engine.eligible("担当C", d(4))


def test_friday_prefers_people_working_on_saturday():
    engine = build_engine(
        {
            ("担当C", d(8)): [Cell(text="ME")],
            ("担当D", d(8)): [Cell(text="有")],
        }
    )
    assert engine.tier("担当C", d(7)) == 0
    assert engine.tier("担当D", d(7)) == 1


def test_operating_room_is_blank_both_rows_or_arm_anywhere():
    """上下段とも空白、または上下どちらかに「アーム」「OP」なら手術室業務。"""
    engine = build_engine(
        {
            ("担当A", d(5)): [],
            ("担当B", d(5)): [Cell(text="Ｏ"), Cell(text="アーム")],
            ("担当C", d(5)): [Cell(text="―/公"), Cell(text="OP")],
            ("担当D", d(5)): [Cell(text="ME"), Cell(text="カテ")],
            ("担当E", d(5)): [Cell(text="公")],
        }
    )
    assert engine.next_day_is_operating_room("担当A", d(4))
    assert engine.next_day_is_operating_room("担当B", d(4))
    assert engine.next_day_is_operating_room("担当C", d(4))
    # 勤務内容がある日、休みの日は手術室ではない
    assert not engine.next_day_is_operating_room("担当D", d(4))
    assert not engine.next_day_is_operating_room("担当E", d(4))


def test_unknown_codes_are_reported():
    """設定のどこにも出てこない記号は、確認事項として拾い出す。"""
    engine = build_engine(
        {
            ("担当C", d(4)): [Cell(text="ME")],
            ("担当D", d(4)): [Cell(text="心カテ待機"), Cell(text="公")],
            ("担当E", d(5)): [Cell(text="心カテ待機")],
        }
    )
    unknown = engine.unknown_codes()
    assert set(unknown) == {"心カテ待機"}
    assert sorted(n for n, _ in unknown["心カテ待機"]) == ["担当D", "担当E"]
