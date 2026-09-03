"""コマンドラインインターフェース。"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from .config import ConfigError, load_config, normalize_name
from .rules import WEEKDAY_JP, RuleEngine
from .solver import solve
from .sample import build_sample
from .template import build_config_text
from .workbook import ScheduleError, detect_year_month, list_member_names, read_schedule
from .writer import write_roster


def parse_month(text: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{4})[-/年]?(\d{1,2})月?", text.strip())
    if not m:
        raise argparse.ArgumentTypeError("--month は 2026-08 の形式で指定してください。")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise argparse.ArgumentTypeError(f"月が不正です: {month}")
    return year, month


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="duty-roster",
        description="勤務割当表から月次のカテ待機表を自動作成する。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="待機表を作成する")
    gen.add_argument("-s", "--schedule", required=True, help="勤務割当表 Excel")
    gen.add_argument("-c", "--config", default="config/roster.yaml", help="設定ファイル")
    gen.add_argument("-m", "--month", type=parse_month, help="対象年月（例 2026-08）。省略時は表題から推定")
    gen.add_argument("-o", "--output", help="出力先 Excel（既定: out/待機表_YYYYMM.xlsx）")

    chk = sub.add_parser("check", help="勤務表の読み取り結果（待機可否）を確認する")
    chk.add_argument("-s", "--schedule", required=True, help="勤務割当表 Excel")
    chk.add_argument("-c", "--config", default="config/roster.yaml", help="設定ファイル")
    chk.add_argument("-m", "--month", type=parse_month, help="対象年月（例 2026-08）")

    init = sub.add_parser("init-config", help="勤務表から設定ファイルのひな型を作る")
    init.add_argument("-s", "--schedule", required=True, help="勤務割当表 Excel")
    init.add_argument("-o", "--output", default="config/roster.yaml", help="出力先 YAML")
    init.add_argument("--names", help="対象者の姓をカンマ区切りで指定（省略時は勤務表から検出）")
    init.add_argument("--force", action="store_true", help="既存ファイルを上書きする")

    smp = sub.add_parser("sample", help="動作確認用のダミー勤務表を作る")
    smp.add_argument("-m", "--month", type=parse_month, required=True, help="対象年月（例 2026-08）")
    smp.add_argument("-o", "--output", default="out/sample_schedule.xlsx", help="出力先 Excel")

    return parser


def resolve_month(args, schedule_path: Path) -> tuple[int, int]:
    if getattr(args, "month", None):
        return args.month
    detected = detect_year_month(schedule_path)
    if detected:
        print(f"対象年月を表題から推定しました: {detected[0]}年{detected[1]}月")
        return detected
    raise SystemExit("対象年月を判別できませんでした。--month 2026-08 の形式で指定してください。")


def cmd_generate(args) -> int:
    cfg = load_config(args.config)
    schedule_path = Path(args.schedule)
    year, month = resolve_month(args, schedule_path)

    schedule = read_schedule(schedule_path, year, month, cfg)
    engine = RuleEngine(cfg, schedule, year, month)
    solution = solve(cfg, engine)

    notes = list(schedule.warnings)
    if engine.exception_days:
        notes.append(
            "全員が不在（一斉「公」など）のため、不在による待機不可を解除した日: "
            + "、".join(f"{d:%m/%d}({WEEKDAY_JP[d.weekday()]})" for d in engine.exception_days)
        )

    output = Path(args.output) if args.output else Path("out") / f"待機表_{year}{month:02d}.xlsx"
    write_roster(output, cfg, engine, solution, warnings=notes)

    print(f"\n{year}年{month}月 待機表")
    print("-" * 42)
    for day in engine.days:
        name = solution.assignment[day]
        mark = "*" if not engine.eligible(name, day) else " "
        print(
            f"{day.day:>2}日({WEEKDAY_JP[day.weekday()]}) {name:<8}{mark}"
            f" {engine.tier_label(name, day)} / 翌日={engine.next_duty_text(name, day)}"
        )
    print("-" * 42)
    quota = cfg.quota(engine.days_in_month)
    print("回数: " + "  ".join(f"{n}{solution.counts[n]}/{quota.get(n, 0)}" for n in engine.members))

    runs = [
        f"{d:%m/%d}-{d + dt.timedelta(days=1):%m/%d} {solution.assignment[d]}"
        for d in engine.days[:-1]
        if solution.assignment[d] == solution.assignment[d + dt.timedelta(days=1)]
    ]
    print("連日: " + ("  ".join(runs) if runs else "なし"))

    for label, items in (
        ("読み取りの注意", notes),
        ("メモ", solution.notes),
        ("ルール違反・要確認", solution.violations),
    ):
        if items:
            print(f"\n[{label}]")
            for item in items:
                print(f"  - {item}")

    print(f"\n出力: {output}")
    return 1 if solution.violations else 0


def cmd_check(args) -> int:
    cfg = load_config(args.config)
    schedule_path = Path(args.schedule)
    year, month = resolve_month(args, schedule_path)
    schedule = read_schedule(schedule_path, year, month, cfg)
    engine = RuleEngine(cfg, schedule, year, month)

    print(f"勤務表: {schedule_path}")
    print(f"検出した対象者: {', '.join(schedule.names_in_sheet)}")
    for w in schedule.warnings:
        print(f"  ! {w}")
    if engine.exception_days:
        print(
            "  ! 全員不在のため不在条件を解除した日: "
            + "、".join(f"{d:%m/%d}" for d in engine.exception_days)
        )

    header = "      " + "".join(f"{d.day:>3}" for d in engine.days)
    print("\n待機可否 (○=可 △=条件付きで可 ×=不可)")
    print(header)
    print("      " + "".join(f"{WEEKDAY_JP[d.weekday()]:>3}" for d in engine.days))
    for name in engine.members:
        row = "".join(f"{engine.availability_mark(name, d):>3}" for d in engine.days)
        print(f"{name:<6}{row}")

    print("\n不可の理由")
    for name in engine.members:
        reasons = [
            f"{d.day}日:{engine.eligibility(name, d).reason}"
            for d in engine.days
            if not engine.eligible(name, d)
        ]
        print(f"  {name}: {', '.join(reasons) if reasons else '（なし）'}")

    conditional = [
        f"{d.day}日 {name}: {engine.eligibility(name, d).note}"
        for name in engine.members
        for d in engine.days
        if engine.eligibility(name, d).conditional
    ]
    if conditional:
        print("\n条件付きで可")
        for line in conditional:
            print(f"  {line}")
    return 0


def cmd_init_config(args) -> int:
    output = Path(args.output)
    if output.exists() and not args.force:
        raise SystemExit(f"{output} は既に存在します。上書きするなら --force を付けてください。")

    if args.names:
        names = [n.strip() for n in args.names.split(",") if n.strip()]
    else:
        detected = list_member_names(args.schedule)
        names = []
        for full in detected:
            surname = full.split(" ")[0] if " " in full else full[:2]
            if surname not in names:
                names.append(surname)
        print(f"勤務表から検出した姓: {', '.join(names)}")
        print("対象外の人が含まれる場合は --names で対象者だけを指定し直してください。")

    if not names:
        raise SystemExit("氏名を検出できませんでした。--names で指定してください。")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_config_text(names), encoding="utf-8")
    print(f"設定ファイルを作成しました: {output}")
    print("※ 氏名を含むファイルです。共有・コミットしないでください（.gitignore 済み）。")
    return 0


def cmd_sample(args) -> int:
    year, month = args.month
    path = build_sample(args.output, year, month)
    print(f"サンプル勤務表を作成しました: {path}")
    print("使い方: duty-roster generate -s {} -c config/roster.example.yaml".format(path))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "generate": cmd_generate,
        "check": cmd_check,
        "init-config": cmd_init_config,
        "sample": cmd_sample,
    }
    try:
        return handlers[args.command](args)
    except (ConfigError, ScheduleError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
