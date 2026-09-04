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
from .rules import RuleEngine
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
    ):
        self.cfg = cfg
        self.engine = engine
        self.primary = primary
        self.fixed = dict(fixed or {})
        self.days = engine.days
        self.members = engine.members
        self.target = cfg.quota(engine.days_in_month)

        conf = cfg.backup
        w = conf.get("weights", {})
        self.w_violation = float(w.get("violation", 1_000_000))
        self.w_quota = float(w.get("quota_deviation", 250))
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
        tier_weights = [float(x) for x in cfg.weights["tier"]]
        fallback = float(cfg.weights["fallback_tier"])
        for day in self.days:
            holiday_workers = set(engine.holiday_workers(day))
            for name in self.members:
                self.ok[(name, day)] = engine.backup_eligible(name, day)
                tier = engine.tier(name, day)
                cost = (
                    tier_weights[tier]
                    if tier is not None and tier < len(tier_weights)
                    else fallback
                )
                if holiday_workers and name not in holiday_workers:
                    cost += float(cfg.weights.get("holiday_not_working", 0))
                self.tier_cost[(name, day)] = cost

    # -- 候補 --------------------------------------------------------------
    def candidates(self, day: dt.date) -> list[str]:
        if day in self.forced:
            return [self.forced[day]]
        primary = self.primary.get(day)
        blocked = self.forbidden.get(primary, set()) if primary else set()
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
            cost += self.tier_cost[(name, day)]

        for name, count in counts.items():
            cost += self.w_quota * (count - self.target.get(name, 0)) ** 2

        # 待機と予備を合算した連続日数
        for name, days in self.combined_days(assignment).items():
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
        for day in self.days:
            name = assignment[day]
            primary = self.primary.get(day)
            if name == primary:
                out.append(f"{day:%m/%d}: 待機と予備が同じ人（{name}）")
            if name in self.forbidden.get(primary or "", set()):
                out.append(f"{day:%m/%d}: 待機が{primary}の日に{name}を予備にしています")
            elig = self.engine.backup_eligibility(name, day)
            if not elig.ok:
                out.append(f"{day:%m/%d} {name}: 予備不可の日に割当（{elig.reason}）")
        for name, days in self.combined_days(assignment).items():
            limit = self.max_run.get(name, 2)
            run, start = 1, days[0] if days else None
            for earlier, later in zip(days, days[1:]):
                if (later - earlier).days == 1:
                    run += 1
                else:
                    if run > limit:
                        out.append(
                            f"{name}: {start:%m/%d}から{run}日連続（上限{limit}日）"
                        )
                    run, start = 1, later
            if run > limit and start:
                out.append(f"{name}: {start:%m/%d}から{run}日連続（上限{limit}日）")
        return out

    def collect_notes(self, assignment: dict[dt.date, str]) -> list[str]:
        out: list[str] = []
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
) -> BackupSolution:
    return BackupSolver(cfg, engine, primary, fixed).solve()
