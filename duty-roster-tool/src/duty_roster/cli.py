"""コマンドラインインターフェース。"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from .config import ConfigError, load_config, normalize_name, parse_day
from .rules import WEEKDAY_JP, RuleEngine
from .backup import solve_backup
from .joint import solve_joint
from .history import History
from .personal import write_personal_rosters
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
    gen.add_argument(
        "--fix",
        action="append",
        metavar="日=氏名",
        help="先に決まっている担当を指定する（例 --fix 5=坂本 --fix 2026-10-12=一戸）。"
        " ルールに関係なくこのとおり入れ、残りを自動で決める。複数回指定できる",
    )
    gen.add_argument(
        "--fix-backup",
        action="append",
        metavar="日=氏名",
        help="予備待機の担当を先に指定する（--fix と同じ書き方）",
    )
    gen.add_argument("--no-backup", action="store_true", help="予備待機表を作らない")
    gen.add_argument(
        "--no-joint",
        action="store_true",
        help="待機と予備を同時に組まず、待機を決めてから予備を決める",
    )
    gen.add_argument("--no-personal", action="store_true", help="個人別待機表を作らない")
    gen.add_argument(
        "--no-history",
        action="store_true",
        help="日曜・祝日の予備の実績を記録しない（試しに作るときに使う）",
    )
    gen.add_argument("--history", help="実績ファイルの場所（既定は設定の history.path）")
    gen.add_argument(
        "-o",
        "--output",
        help="出力先。ファイル名でもフォルダでも可。省略時は設定の output.directory を使う",
    )

    chk = sub.add_parser("check", help="勤務表の読み取り結果（待機可否）を確認する")
    chk.add_argument("-s", "--schedule", required=True, help="勤務割当表 Excel")
    chk.add_argument("-c", "--config", default="config/roster.yaml", help="設定ファイル")
    chk.add_argument("-m", "--month", type=parse_month, help="対象年月（例 2026-08）")

    init = sub.add_parser("init-config", help="勤務表から設定ファイルのひな型を作る")
    init.add_argument("-s", "--schedule", required=True, help="勤務割当表 Excel")
    init.add_argument("-o", "--output", default="config/roster.yaml", help="出力先 YAML")
    init.add_argument("--names", help="対象者の姓をカンマ区切りで指定（省略時は勤務表から検出）")
    init.add_argument("--force", action="store_true", help="既存ファイルを上書きする")

    hist = sub.add_parser("history", help="日曜・祝日の予備の実績を見る／消す")
    hist.add_argument("-c", "--config", default="config/roster.yaml", help="設定ファイル")
    hist.add_argument("--path", help="実績ファイルの場所")
    hist.add_argument("--reset", action="store_true", help="実績を消して最初からにする")

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


def resolve_output(given: str | None, cfg, year: int, month: int) -> Path:
    """出力先を決める。フォルダだけ渡された場合は既定のファイル名を付ける。"""
    if not given:
        return cfg.output_path(year, month)
    path = Path(given).expanduser()
    if path.is_dir() or given.endswith(("/", "\\")) or not path.suffix:
        filename = cfg.output_path(year, month).name
        return (path / filename).resolve()
    return path.resolve()


def parse_fixed(
    entries: list[str] | None, cfg, year: int, month: int, source=None
) -> dict[dt.date, str]:
    """--fix と設定の指定をまとめる（--fix が優先）。"""
    fixed = (source or cfg.fixed_assignments)(year, month)
    for entry in entries or []:
        if "=" not in entry:
            raise SystemExit(f"--fix は 日=氏名 の形式で指定してください: {entry}")
        raw_day, name = (part.strip() for part in entry.split("=", 1))
        try:
            day = parse_day(raw_day, year, month)
        except ValueError as exc:
            raise SystemExit(f"--fix の日付を解釈できません: {raw_day}（{exc}）") from exc
        fixed[day] = name

    known = {normalize_name(n): n for n in cfg.member_names}
    resolved: dict[dt.date, str] = {}
    for day, name in fixed.items():
        key = normalize_name(name)
        if key not in known:
            raise SystemExit(f"{day:%m/%d} に指定された「{name}」は対象者にいません。")
        if not (day.year == year and day.month == month):
            raise SystemExit(f"{day} は対象月（{year}年{month}月）の日付ではありません。")
        resolved[day] = known[key]
    return resolved


def cmd_generate(args) -> int:
    cfg = load_config(args.config)
    schedule_path = Path(args.schedule)
    year, month = resolve_month(args, schedule_path)

    schedule = read_schedule(schedule_path, year, month, cfg)
    engine = RuleEngine(cfg, schedule, year, month)
    fixed = parse_fixed(getattr(args, "fix", None), cfg, year, month)
    if fixed:
        print("先に決めた担当: " + "、".join(f"{d:%m/%d}={n}" for d, n in sorted(fixed.items())))
    make_backup = cfg.backup_enabled and not args.no_backup
    joint = make_backup and cfg.joint_enabled and not getattr(args, "no_joint", False)
    prebuilt_backup = None
    if joint:
        fixed_backup, past, _, _ = _backup_inputs(args, cfg, year, month)
        print("待機と予備を同時に組みます（--no-joint で待機→予備の順に戻せます）")
        solution, prebuilt_backup = solve_joint(cfg, engine, fixed, fixed_backup, past)
    else:
        solution = solve(cfg, engine, fixed)

    notes = list(schedule.warnings) + unknown_code_notes(engine)
    if engine.exception_days:
        notes.append(
            "全員が不在（一斉「公」など）のため、不在による待機不可を解除した日: "
            + "、".join(f"{d:%m/%d}({WEEKDAY_JP[d.weekday()]})" for d in engine.exception_days)
        )

    output = resolve_output(args.output, cfg, year, month)
    write_roster(output, cfg, engine, solution, warnings=notes, fixed=fixed)

    print(f"\n{year}年{month}月 待機表")
    print("-" * 42)
    for day in engine.days:
        name = solution.assignment[day]
        if day in fixed:
            print(f"{day.day:>2}日({WEEKDAY_JP[day.weekday()]}) {name:<8}  【指定】")
            continue
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

    violations = list(solution.violations)
    backup_assignment: dict[dt.date, str] = {}
    if make_backup:
        backup_violations, backup_assignment = _make_backup(
            args, cfg, engine, solution, notes, year, month, prebuilt_backup
        )
        violations += backup_violations

    if not args.no_personal:
        personal = cfg.personal_output_path(year, month)
        if args.output:
            given = Path(args.output).expanduser()
            directory = given if (given.is_dir() or not given.suffix) else given.parent
            personal = (directory / personal.name).resolve()
        write_personal_rosters(personal, cfg, engine, solution.assignment, backup_assignment)
        print(f"個人別待機表: {personal}")
    return 1 if violations else 0


def unknown_code_notes(engine) -> list[str]:
    """勤務表に出てきた「意味の分からない記号」を確認事項として書き出す。"""
    unknown = engine.unknown_codes()
    if not unknown:
        return []
    out = [
        "見慣れない記号がありました。意味を教えてください"
        "（現状は手術室勤務として扱っています）:"
    ]
    for code, where in sorted(unknown.items(), key=lambda x: (-len(x[1]), x[0])):
        span = "、".join(f"{d:%m/%d}{n}" for n, d in where[:6])
        more = f" ほか{len(where) - 6}件" if len(where) > 6 else ""
        out.append(f"  「{code}」{len(where)}件: {span}{more}")
    return out


def _backup_availability_view(engine):
    """可否一覧の表示用。平日で翌日が手術室の人も△として見せる。"""
    from .rules import SAT, SUN, Eligibility

    def view(name, day):
        elig = engine.backup_eligibility(name, day)
        if elig.ok and not elig.conditional and day.weekday() not in (SAT, SUN):
            label = engine.next_day_last_resort_label(name, day)
            if label:
                return Eligibility(
                    True, penalty=1.0, note=f"{label}（他に組めない場合の候補）"
                )
        return elig

    return view


def _backup_inputs(args, cfg, year, month, announce=True):
    """予備を組むための入力（先に決めた予備・日曜祝日の実績）を集める。"""
    fixed_backup = parse_fixed(
        getattr(args, "fix_backup", None), cfg, year, month, source=cfg.fixed_backup_assignments
    )
    history_path = Path(args.history).expanduser() if args.history else cfg.history_path
    use_history = cfg.history_enabled and not args.no_history
    history = History.load(history_path)
    past = history.holiday_backup_totals(exclude_month=(year, month)) if use_history else {}
    if past and announce:
        print(
            "\nこれまでの日曜・祝日の予備（"
            + "・".join(history.recorded_months())
            + "）: "
            + " ".join(f"{n}{c}" for n, c in sorted(past.items()))
        )
    return fixed_backup, past, history, use_history


def _make_backup(args, cfg, engine, solution, notes, year, month, backup=None):
    """予備待機表を作る。戻り値は (要確認事項, 割り当て)。"""
    fixed_backup, past, history, use_history = _backup_inputs(
        args, cfg, year, month, announce=backup is None
    )
    if backup is None:
        backup = solve_backup(cfg, engine, solution.assignment, fixed_backup, past)

    print(f"\n{year}年{month}月 予備待機表")
    print("-" * 42)
    for day in engine.days:
        name = backup.assignment[day]
        tag = "【指定】" if day in fixed_backup else (
            "【自動：待機が" + solution.assignment[day] + "のため】"
            if day in backup.forced
            else engine.tier_label(name, day)
        )
        print(
            f"{day.day:>2}日({WEEKDAY_JP[day.weekday()]}) 待機={solution.assignment[day]:<6}"
            f" 予備={name:<6} {tag}"
        )
    print("-" * 42)
    quota = cfg.quota(engine.days_in_month)
    print("予備回数: " + "  ".join(f"{n}{backup.counts[n]}/{quota.get(n, 0)}" for n in engine.members))

    solver_view = __import__("duty_roster.backup", fromlist=["BackupSolver"]).BackupSolver(
        cfg, engine, solution.assignment, fixed_backup, past
    )
    holiday_counts = solver_view.holiday_counts(backup.assignment)
    pool = [n for n in engine.members if n not in cfg.backup_holiday_fairness_ignore]
    print(
        "日曜・祝日の予備（今月／通算）: "
        + " ".join(
            f"{n}{holiday_counts.get(n, 0)}/{past.get(n, 0) + holiday_counts.get(n, 0)}"
            for n in pool
        )
    )

    if use_history:
        history.record_holiday_backup(
            year, month, backup.assignment, engine.is_red_day
        )
        history.save()
        print(f"実績を記録しました: {history.path}")

    for label, items in (("メモ", backup.notes), ("ルール違反・要確認", backup.violations)):
        if items:
            print(f"\n[予備 {label}]")
            for item in items:
                print(f"  - {item}")

    output = cfg.backup_output_path(year, month)
    if args.output:
        given = Path(args.output).expanduser()
        directory = given if (given.is_dir() or not given.suffix) else given.parent
        output = (directory / cfg.backup_output_path(year, month).name).resolve()
    write_roster(
        output,
        cfg,
        engine,
        backup,
        warnings=notes,
        fixed=fixed_backup,
        sheet_name="予備待機表",
        title="カテ予備待機表",
        partner=solution.assignment,
        partner_label="待機者",
        availability_fn=_backup_availability_view(engine),
        candidates_fn=lambda day: [
            n for n in engine.members if engine.backup_eligible(n, day)
        ],
        name_color_fn=lambda day, name: (
            cfg.output.get("backup_operating_room_color", "FFFF0000")
            if engine.next_day_is_operating_room(name, day)
            else None
        ),
    )
    print(f"\n出力: {output}")
    return backup.violations, backup.assignment


def cmd_check(args) -> int:
    cfg = load_config(args.config)
    schedule_path = Path(args.schedule)
    year, month = resolve_month(args, schedule_path)
    schedule = read_schedule(schedule_path, year, month, cfg)
    engine = RuleEngine(cfg, schedule, year, month)

    print(f"勤務表: {schedule_path}")
    print(f"検出した対象者: {', '.join(schedule.names_in_sheet)}")
    for w in schedule.warnings + unknown_code_notes(engine):
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


def cmd_history(args) -> int:
    cfg = load_config(args.config)
    path = Path(args.path).expanduser() if args.path else cfg.history_path
    history = History.load(path)

    if args.reset:
        if not path.exists():
            print(f"実績ファイルはまだありません: {path}")
            return 0
        path.unlink()
        print(f"実績を消しました: {path}")
        print("次に作る月から、日曜・祝日の予備の回数を数え直します。")
        return 0

    months = history.recorded_months()
    if not months:
        print(f"記録はまだありません（{path}）")
        return 0
    print(f"記録のある月: {'、'.join(months)}")
    totals = history.holiday_backup_totals()
    print("日曜・祝日の予備の通算回数:")
    for name in sorted(totals, key=lambda n: (-totals[n], n)):
        print(f"  {name}: {totals[name]}")
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
        "history": cmd_history,
        "sample": cmd_sample,
    }
    try:
        return handlers[args.command](args)
    except (ConfigError, ScheduleError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
