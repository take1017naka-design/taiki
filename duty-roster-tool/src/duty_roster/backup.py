"""予備待機表の割り当て。

待機表が決まったあとに、同じ日の「もう1人」を決める。

ルール:

* 待機者とは別の人
* 待機者が backup_dependents（中沢・鈴木）の日は、必ず backup_anchor（中村）
* 待機者ごとに、予備に入れない人を設定できる（forbidden_pairs）
* 待機と予備を**合算した**連続日数に上限を設ける（既定2日、例外で3日）
* 回数は待機表と同じ目標回数に近づける（ハード制約ではない）
* 優先順位（翌日の勤務内容）は待機表と同じものを使う
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field

from .config import Config
from .rules import SAT, SUN, RuleEngine
from .solver import Solution, week_index


@dataclass
class BackupSolution:
    assignment: dict[dt.date, str]
    cost: float
    counts: dict[str, int]
    forced: dict[dt.date, str] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class BackupSolver:
    def __init__(
        self,
        cfg: Config,
        engine: RuleEngine,
        primary: dict[dt.date, str],
        fixed: dict[dt.date, str] | None = None,
        holiday_history: dict[str, int] | None = None,
    ):
        self.cfg = cfg
        self.engine = engine
        self.primary = primary
        self.fixed = dict(fixed or {})
        self.days = engine.days
        self.members = engine.members
        self.target = cfg.quota(engine.days_in_month)
        self.quota_ignore = cfg.backup_quota_ignore
        self.quota_priority = cfg.backup_quota_priority
        self.consecutive_ignore = cfg.backup_consecutive_ignore
        self.report_threshold = cfg.backup_consecutive_report_threshold
        # 土日は予備に入れない人／祝日に入れたら要相談の人
        self.weekend_excluded = cfg.backup_weekend_excluded
        self.holiday_consult = cfg.backup_holiday_consult
        self.w_holiday_consult = float(
            cfg.backup.get("weights", {}).get("holiday_consult", 2000)
        )
        # 日曜・祝日の予備を年間で均等にする
        self.holiday_days = [d for d in engine.days if engine.is_red_day(d)]
        self.holiday_history = dict(holiday_history or {})
        self.holiday_pool = [
            n for n in self.members if n not in cfg.backup_holiday_fairness_ignore
        ]
        self.w_holiday_fair = float(
            cfg.backup.get("weights", {}).get("holiday_fairness", 400)
        )

        conf = cfg.backup
        w = conf.get("weights", {})
        self.w_violation = float(w.get("violation", 1_000_000))
        self.w_quota = float(w.get("quota_deviation", 250))
        self.w_quota_priority = float(w.get("quota_deviation_priority", 40000))
        self.w_consec = float(w.get("consecutive", 600))
        self.max_run = {n: cfg.backup_max_run(n) for n in self.members}
        self.forbidden = cfg.backup_forbidden_pairs

        self.anchor = cfg.backup_anchor
        self.dependents = set(cfg.backup_dependents)
        self.force_anchor = bool(conf.get("forced_anchor_for_dependents", True))

        # 待機者ごとの担当日（連続日数の判定に使う）
        self.primary_days: dict[str, set[dt.date]] = {n: set() for n in self.members}
        for day, name in primary.items():
            self.primary_days.setdefault(name, set()).add(day)

        self.forced: dict[dt.date, str] = {}
        if self.force_anchor and self.anchor:
            for day in self.days:
                if primary.get(day) in self.dependents:
                    self.forced[day] = self.anchor
        self.forced.update(self.fixed)

        self.tier_cost: dict[tuple[str, dt.date], float] = {}
        self.ok: dict[tuple[str, dt.date], bool] = {}
        # 最後の段（翌日が手術室＝OP・アーム・空白）と該当なしだけを重くする
        multiplier = float(conf.get("last_resort_multiplier", 40))
        raw_tiers = [float(x) for x in cfg.weights["tier"]]
        tier_weights = raw_tiers[:-1] + [raw_tiers[-1] * multiplier]
        fallback = float(cfg.weights["fallback_tier"]) * multiplier
        self.sunday_once_each = bool(conf.get("sunday_once_each", True))
        self.w_sunday_repeat = float(w.get("sunday_repeat", 6000))
        self.sundays = [d for d in engine.days if d.weekday() == SUN]
        for day in self.days:
            holiday_workers = set(engine.holiday_workers(day))
            for name in self.members:
                elig = engine.backup_eligibility(name, day)
                self.ok[(name, day)] = elig.ok
                tier = engine.tier(name, day)
                cost = (
                    tier_weights[tier]
                    if tier is not None and tier < len(tier_weights)
                    else fallback
                )
                if holiday_workers and name not in holiday_workers:
                    cost += float(cfg.weights.get("holiday_not_working", 0))
                # 前日(土)不在・翌日手術室などの「最後の手段」ぶん
                cost += elig.penalty
                self.tier_cost[(name, day)] = cost

    # -- 候補 --------------------------------------------------------------
    def excluded_today(self, day: dt.date) -> set[str]:
        """その日、予備の対象から外れる人（土日限定。祝日は要相談として残す）。"""
        if self.engine.is_holiday(day):
            return set()
        return self.weekend_excluded if day.weekday() in (SAT, SUN) else set()

    def candidates(self, day: dt.date) -> list[str]:
        if day in self.forced:
            return [self.forced[day]]
        primary = self.primary.get(day)
        blocked = set(self.forbidden.get(primary, set()) if primary else set())
        blocked |= self.excluded_today(day)
        pool = [
            n
            for n in self.members
            if n != primary and n not in blocked and self.ok[(n, day)]
        ]
        if pool:
            return pool
        # 誰も残らない日は、可否を無視してでも埋める（違反として報告する）
        return [n for n in self.members if n != primary and n not in blocked] or list(self.members)

    # -- 評価 --------------------------------------------------------------
    def combined_days(self, assignment: dict[dt.date, str]) -> dict[str, list[dt.date]]:
        out = {n: set(self.primary_days.get(n, set())) for n in self.members}
        for day, name in assignment.items():
            out.setdefault(name, set()).add(day)
        return {n: sorted(days) for n, days in out.items()}

    def evaluate(self, assignment: dict[dt.date, str]) -> float:
        cost = 0.0
        counts = {n: 0 for n in self.members}
        for day, name in assignment.items():
            counts[name] = counts.get(name, 0) + 1
            if not self.ok[(name, day)]:
                cost += self.w_violation
            if name == self.primary.get(day):
                cost += self.w_violation
            if name in self.forbidden.get(self.primary.get(day, ""), set()):
                cost += self.w_violation
            if day in self.forced and name != self.forced[day]:
                cost += self.w_violation
            if name in self.excluded_today(day):
                cost += self.w_violation
            if self.engine.is_holiday(day) and name in self.holiday_consult:
                cost += self.w_holiday_consult
            cost += self.tier_cost[(name, day)]

        for name, count in counts.items():
            if name in self.quota_ignore:
                continue  # 回数の目標を見ない人（自動確定の日が多いため）
            weight = (
                self.w_quota_priority if name in self.quota_priority else self.w_quota
            )
            cost += weight * (count - self.target.get(name, 0)) ** 2

        # 日曜の予備も月内で1人1回ずつ（無理なら許容してコストを載せる）
        if self.sunday_once_each and self.w_sunday_repeat:
            seen: dict[str, int] = {}
            for day in self.sundays:
                name = assignment.get(day)
                if name:
                    seen[name] = seen.get(name, 0) + 1
            cost += self.w_sunday_repeat * sum(c - 1 for c in seen.values() if c > 1)

        # 日曜の予備も月内で1人1回ずつ（無理なら許容してコストを載せる）
        if self.sunday_once_each and self.w_sunday_repeat:
            seen: dict[str, int] = {}
            for day in self.sundays:
                name = assignment.get(day)
                if name:
                    seen[name] = seen.get(name, 0) + 1
            cost += self.w_sunday_repeat * sum(c - 1 for c in seen.values() if c > 1)

        # 日曜・祝日の予備を年間で均等に（これまでの実績を含めて評価する）
        if self.w_holiday_fair and self.holiday_pool and self.holiday_days:
            totals = {
                n: self.holiday_history.get(n, 0)
                for n in self.holiday_pool
            }
            for day in self.holiday_days:
                name = assignment.get(day)
                if name in totals:
                    totals[name] += 1
            mean = sum(totals.values()) / len(totals)
            cost += self.w_holiday_fair * sum((v - mean) ** 2 for v in totals.values())

        # 待機と予備を合算した連続日数
        for name, days in self.combined_days(assignment).items():
            if name in self.consecutive_ignore:
                continue  # 連続を見ない人
            limit = self.max_run.get(name, 2)
            run = 1
            for earlier, later in zip(days, days[1:]):
                if (later - earlier).days == 1:
                    run += 1
                    cost += self.w_consec
                else:
                    if run > limit:
                        cost += self.w_violation * (run - limit)
                    run = 1
            if run > limit:
                cost += self.w_violation * (run - limit)
        return cost

    # -- 探索 --------------------------------------------------------------
    def solve(self) -> BackupSolution:
        conf = self.cfg.backup.get("search", {})
        rng = random.Random(int(self.cfg.search["seed"]) + 7)
        restarts = max(1, int(conf.get("restarts", 8)))
        iterations = max(1, int(conf.get("iterations", 2500)))
        open_days = [d for d in self.days if d not in self.forced]

        best: dict[dt.date, str] | None = None
        best_cost = float("inf")
        for _ in range(restarts):
            assignment = dict(self.forced)
            for day in open_days:
                assignment[day] = rng.choice(self.candidates(day))
            cost = self.evaluate(assignment)
            for _ in range(iterations):
                if not open_days:
                    break
                day = open_days[rng.randrange(len(open_days))]
                current = assignment[day]
                for name in self.candidates(day):
                    if name == current:
                        continue
                    assignment[day] = name
                    trial = self.evaluate(assignment)
                    if trial < cost - 1e-9:
                        cost, current = trial, name
                    else:
                        assignment[day] = current
            if cost < best_cost:
                best, best_cost = dict(assignment), cost

        assert best is not None
        counts = {n: 0 for n in self.members}
        for name in best.values():
            counts[name] = counts.get(name, 0) + 1
        return BackupSolution(
            assignment=best,
            cost=best_cost,
            counts=counts,
            forced=dict(self.forced),
            violations=self.collect_violations(best),
            notes=self.collect_notes(best),
        )

    # -- 検証 --------------------------------------------------------------
    def collect_violations(self, assignment: dict[dt.date, str]) -> list[str]:
        out: list[str] = []
        if self.sunday_once_each:
            seen: dict[str, list[dt.date]] = {}
            for day in self.sundays:
                seen.setdefault(assignment[day], []).append(day)
            for name, days in seen.items():
                if len(days) > 1:
                    out.append(
                        f"日曜の予備が重複: {name}（"
                        + "、".join(f"{d:%m/%d}" for d in days)
                        + "）"
                    )

        counts = self.counts_of(assignment)
        for name in sorted(self.quota_priority):
            target = self.target.get(name, 0)
            if counts.get(name, 0) != target:
                out.append(
                    f"{name}: 予備が {counts.get(name, 0)} 回で目標 {target} 回に届いていません"
                )

        for day in self.days:
            name = assignment[day]
            primary = self.primary.get(day)
            if name == primary:
                out.append(f"{day:%m/%d}: 待機と予備が同じ人（{name}）")
            if name in self.forbidden.get(primary or "", set()):
                out.append(f"{day:%m/%d}: 待機が{primary}の日に{name}を予備にしています")
            if name in self.excluded_today(day):
                out.append(f"{day:%m/%d}: {name}は土日の予備の対象外です")
            if self.engine.is_holiday(day) and name in self.holiday_consult:
                out.append(
                    f"{day:%m/%d}(祝): 予備が{name}です。祝日のため相談してください"
                )
            elig = self.engine.backup_eligibility(name, day)
            if not elig.ok:
                out.append(f"{day:%m/%d} {name}: 予備不可の日に割当（{elig.reason}）")
        for name, days in self.combined_days(assignment).items():
            if not days:
                continue
            skip = name in self.consecutive_ignore
            limit = self.report_threshold - 1 if skip else self.max_run.get(name, 2)
            suffix = (
                "（待機＋予備。相談してください）" if skip else f"（上限{limit}日）"
            )
            run, start = 1, days[0]
            for earlier, later in zip(days, days[1:]):
                if (later - earlier).days == 1:
                    run += 1
                else:
                    if run > limit:
                        out.append(f"{name}: {start:%m/%d}から{run}日連続{suffix}")
                    run, start = 1, later
            if run > limit:
                out.append(f"{name}: {start:%m/%d}から{run}日連続{suffix}")
        return out

    def holiday_counts(self, assignment: dict[dt.date, str]) -> dict[str, int]:
        counts = {n: 0 for n in self.members}
        for day in self.holiday_days:
            name = assignment.get(day)
            if name:
                counts[name] = counts.get(name, 0) + 1
        return counts

    def collect_notes(self, assignment: dict[dt.date, str]) -> list[str]:
        out: list[str] = []
        for day in self.days:
            elig = self.engine.backup_eligibility(assignment[day], day)
            if elig.conditional:
                out.append(f"{day:%m/%d} {assignment[day]}: {elig.note}")
        if self.forced:
            forced_by_rule = {d: n for d, n in self.forced.items() if d not in self.fixed}
            if forced_by_rule:
                out.append(
                    f"待機が{'・'.join(sorted(self.dependents))}の日は{self.anchor}が予備: "
                    + "、".join(f"{d:%m/%d}" for d in sorted(forced_by_rule))
                )
            if self.fixed:
                out.append(
                    "先に決めた予備: "
                    + "、".join(f"{d:%m/%d}={n}" for d, n in sorted(self.fixed.items()))
                )
        for name, days in self.combined_days(assignment).items():
            if name in self.consecutive_ignore:
                continue
            runs = [
                f"{a:%m/%d}-{b:%m/%d}"
                for a, b in zip(days, days[1:])
                if (b - a).days == 1
            ]
            if runs:
                out.append(f"{name}: 待機と予備が連日 {'、'.join(runs)}")
        return out

    def counts_of(self, assignment: dict[dt.date, str]) -> dict[str, int]:
        counts = {n: 0 for n in self.members}
        for name in assignment.values():
            counts[name] = counts.get(name, 0) + 1
        return counts


def solve_backup(
    cfg: Config,
    engine: RuleEngine,
    primary: dict[dt.date, str],
    fixed: dict[dt.date, str] | None = None,
    holiday_history: dict[str, int] | None = None,
) -> BackupSolution:
    return BackupSolver(cfg, engine, primary, fixed, holiday_history).solve()
