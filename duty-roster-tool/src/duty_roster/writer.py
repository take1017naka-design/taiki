"""待機表 Excel の書き出し。"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .config import Config
from .rules import SAT, SUN, WEEKDAY_JP, RuleEngine
from .solver import Solution

THIN = Side(style="thin", color="FF999999")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center")


def _day_font_color(engine: RuleEngine, day: dt.date, out: dict[str, str]) -> str:
    if engine.is_red_day(day):
        return out["sunday_font_color"]
    if day.weekday() == SAT:
        return out["saturday_font_color"]
    return out["weekday_font_color"]


def write_roster(
    path: str | Path,
    cfg: Config,
    engine: RuleEngine,
    solution: Solution,
    warnings: list[str] | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    _sheet_calendar(wb, cfg, engine, solution)
    _sheet_list(wb, engine, solution)
    _sheet_summary(wb, cfg, engine, solution)
    _sheet_availability(wb, engine)
    _sheet_notes(wb, solution, warnings or [])

    wb.save(path)
    return path


def _sheet_calendar(wb: Workbook, cfg: Config, engine: RuleEngine, solution: Solution) -> None:
    ws = wb.active
    ws.title = "待機表"
    out = cfg.output

    ws.cell(row=1, column=1, value=f"{engine.year}年{engine.month}月　カテ待機表").font = Font(
        size=14, bold=True
    )
    header = ["日", "月", "火", "水", "木", "金", "土"]
    for i, label in enumerate(header, start=1):
        cell = ws.cell(row=3, column=i, value=label)
        cell.alignment = CENTER
        cell.border = BOX
        color = (
            out["sunday_font_color"]
            if i == 1
            else out["saturday_font_color"] if i == 7 else out["weekday_font_color"]
        )
        cell.font = Font(bold=True, color=color)
        cell.fill = PatternFill("solid", fgColor="FFF2F2F2")
        ws.column_dimensions[get_column_letter(i)].width = 13

    # 日曜始まりの列位置（Python の weekday は月=0 なので +1 して 7 で割る）
    def column_of(day: dt.date) -> int:
        return (day.weekday() + 1) % 7 + 1

    row = 4
    prev_col = None
    for day in engine.days:
        col = column_of(day)
        if prev_col is not None and col <= prev_col:
            row += 2
        prev_col = col
        date_cell = ws.cell(row=row, column=col, value=day.day)
        date_cell.font = Font(bold=True, color=_day_font_color(engine, day, out))
        date_cell.alignment = Alignment(horizontal="left", vertical="center")
        date_cell.border = Border(left=THIN, right=THIN, top=THIN)

        name_cell = ws.cell(row=row + 1, column=col, value=solution.assignment[day])
        name_cell.alignment = CENTER
        name_cell.border = Border(left=THIN, right=THIN, bottom=THIN)
        if engine.is_holiday(day):
            date_cell.fill = PatternFill("solid", fgColor="FFFDE9E9")
            name_cell.fill = PatternFill("solid", fgColor="FFFDE9E9")

    for r in range(4, row + 2, 2):
        ws.row_dimensions[r].height = 16
        ws.row_dimensions[r + 1].height = 22

    ws.cell(row=row + 3, column=1, value="※ 日付の色: 平日=黒 / 土曜=青 / 日曜・祝日=赤").font = Font(
        size=9, color="FF808080"
    )


def _sheet_list(wb: Workbook, engine: RuleEngine, solution: Solution) -> None:
    ws = wb.create_sheet("一覧")
    headers = ["日付", "曜日", "待機者", "採用した優先順位", "翌日の勤務", "同日の他候補"]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="FFF2F2F2")
        c.border = BOX
    widths = [12, 6, 12, 20, 22, 40]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    for r, day in enumerate(engine.days, start=2):
        name = solution.assignment[day]
        others = [n for n in engine.candidates(day) if n != name]
        values = [
            day.strftime("%Y/%m/%d"),
            WEEKDAY_JP[day.weekday()],
            name,
            engine.tier_label(name, day),
            engine.next_duty_text(name, day),
            "・".join(others),
        ]
        for i, v in enumerate(values, start=1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.border = BOX
            if i == 2:
                cell.alignment = CENTER
    ws.freeze_panes = "A2"


def _sheet_summary(wb: Workbook, cfg: Config, engine: RuleEngine, solution: Solution) -> None:
    ws = wb.create_sheet("集計")
    quota = cfg.quota(engine.days_in_month)
    headers = ["氏名", "目標回数", "実績回数", "差", "土日祝", "連日", "待機日"]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="FFF2F2F2")
        c.border = BOX
    for i, w in enumerate([12, 10, 10, 8, 8, 8, 46], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    days_of = {n: [] for n in engine.members}
    for day in engine.days:
        days_of[solution.assignment[day]].append(day)

    for r, name in enumerate(engine.members, start=2):
        mine = days_of[name]
        holiday_count = sum(1 for d in mine if engine.is_red_day(d) or d.weekday() == SAT)
        consec = sum(1 for d in mine if (d + dt.timedelta(days=1)) in mine)
        target = quota.get(name, 0)
        values = [
            name,
            target,
            len(mine),
            len(mine) - target,
            holiday_count,
            consec,
            " ".join(f"{d.day}({WEEKDAY_JP[d.weekday()]})" for d in mine),
        ]
        for i, v in enumerate(values, start=1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.border = BOX
            if i == 4 and v != 0:
                cell.font = Font(color="FFFF0000", bold=True)


def _sheet_availability(wb: Workbook, engine: RuleEngine) -> None:
    """読み取り結果の目視確認用。○=待機可 / 記号=不可理由。"""
    ws = wb.create_sheet("可否一覧")
    ws.cell(row=1, column=1, value="待機可否（○=可、△=条件付きで可、×=不可・下に理由）").font = Font(bold=True)
    ws.cell(row=2, column=1, value="氏名").font = Font(bold=True)
    for i, day in enumerate(engine.days, start=2):
        c = ws.cell(row=2, column=i, value=day.day)
        c.font = Font(bold=True)
        c.alignment = CENTER
        ws.column_dimensions[get_column_letter(i)].width = 4.5
    ws.column_dimensions["A"].width = 12

    for r, name in enumerate(engine.members, start=3):
        ws.cell(row=r, column=1, value=name).font = Font(bold=True)
        for i, day in enumerate(engine.days, start=2):
            elig = engine.eligibility(name, day)
            cell = ws.cell(row=r, column=i, value=engine.availability_mark(name, day))
            cell.alignment = CENTER
            if not elig.ok:
                cell.font = Font(color="FF999999")
            elif elig.conditional:
                cell.font = Font(color="FFC55A11", bold=True)
            if engine.is_yellow(name, day):
                cell.fill = PatternFill("solid", fgColor="FFFFFF00")
    ws.freeze_panes = "B3"

    start = len(engine.members) + 5
    ws.cell(row=start, column=1, value="不可・条件付きの理由").font = Font(bold=True)
    r = start + 1
    for name in engine.members:
        for day in engine.days:
            elig = engine.eligibility(name, day)
            if elig.ok and not elig.conditional:
                continue
            ws.cell(row=r, column=1, value=f"{day:%m/%d}")
            ws.cell(row=r, column=2, value=name)
            ws.cell(row=r, column=3, value="△" if elig.conditional else "×")
            ws.cell(row=r, column=4, value=elig.note if elig.conditional else elig.reason)
            r += 1


def _sheet_notes(wb: Workbook, solution: Solution, warnings: list[str]) -> None:
    ws = wb.create_sheet("確認事項")
    ws.column_dimensions["A"].width = 90
    row = 1
    for title, items in (
        ("ルール違反・要確認", solution.violations),
        ("メモ", solution.notes),
        ("読み取りの注意", warnings),
    ):
        ws.cell(row=row, column=1, value=title).font = Font(bold=True, size=12)
        row += 1
        if not items:
            ws.cell(row=row, column=1, value="（なし）")
            row += 2
            continue
        for item in items:
            ws.cell(row=row, column=1, value=f"・{item}")
            row += 1
        row += 1
